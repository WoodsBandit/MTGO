"""MTG Engine V3 - Combat System (CR 506-511)

Complete implementation of the Magic: The Gathering combat phase including:
- All combat steps per Comprehensive Rules 506-511
- First strike and double strike (two damage steps)
- Trample (excess damage assignment)
- Deathtouch (1 damage = lethal)
- Lifelink (controller gains life)
- Flying / Reach (evasion mechanics)
- Menace (must be blocked by 2+ creatures)
- Vigilance (doesn't tap to attack)
- Multiple blockers and damage assignment order
- Complete damage assignment algorithm
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any, TYPE_CHECKING
from enum import Enum, auto

if TYPE_CHECKING:
    from .game import Game
    from .objects import Permanent
    from .player import Player

# Type aliases
ObjectId = int
PlayerId = int


# =============================================================================
# COMBAT DATA CLASSES
# =============================================================================

@dataclass(slots=True)
class AttackDeclaration:
    """
    Declaration of an attacker (CR 508.1)

    Represents a creature attacking a player or planeswalker.

    Attributes:
        attacker: The attacking creature (Permanent)
        defending: The target being attacked (Player or Planeswalker permanent)
        is_legal: Whether this attack declaration is currently legal
    """
    attacker: Any  # Permanent
    defending: Any  # Player or Planeswalker Permanent
    is_legal: bool = True

    @property
    def attacker_id(self) -> ObjectId:
        """Get the attacker's object ID"""
        return self.attacker.object_id if hasattr(self.attacker, 'object_id') else 0

    @property
    def defending_id(self) -> Any:
        """Get the defending entity's ID (player ID or object ID)"""
        if hasattr(self.defending, 'object_id'):
            return self.defending.object_id
        if hasattr(self.defending, 'player_id'):
            return self.defending.player_id
        return None

    def is_attacking_player(self) -> bool:
        """Check if attacking a player (not planeswalker)"""
        return hasattr(self.defending, 'player_id')

    def is_attacking_planeswalker(self) -> bool:
        """Check if attacking a planeswalker"""
        if hasattr(self.defending, 'characteristics'):
            return self.defending.characteristics.is_planeswalker()
        return False


@dataclass(slots=True)
class BlockDeclaration:
    """
    Declaration of a blocker (CR 509.1)

    Represents a creature blocking an attacker.

    Attributes:
        blocker: The blocking creature (Permanent)
        blocking: The attacker being blocked (Permanent)
        is_legal: Whether this block declaration is currently legal
    """
    blocker: Any  # Permanent
    blocking: Any  # Permanent (the attacker)
    is_legal: bool = True

    @property
    def blocker_id(self) -> ObjectId:
        """Get the blocker's object ID"""
        return self.blocker.object_id if hasattr(self.blocker, 'object_id') else 0

    @property
    def blocking_id(self) -> ObjectId:
        """Get the blocked attacker's object ID"""
        return self.blocking.object_id if hasattr(self.blocking, 'object_id') else 0


@dataclass(slots=True)
class DamageAssignment:
    """
    How damage is assigned from one source (CR 510.1)

    Represents damage being dealt from a source to a target.

    Attributes:
        source: The damage source (Permanent)
        target: The damage recipient (Permanent or Player)
        amount: The amount of damage being dealt
        is_combat: Whether this is combat damage
    """
    source: Any  # Permanent
    target: Any  # Permanent or Player
    amount: int
    is_combat: bool = True

    @property
    def source_id(self) -> ObjectId:
        """Get the source's object ID"""
        return self.source.object_id if hasattr(self.source, 'object_id') else 0

    @property
    def target_id(self) -> Any:
        """Get the target's ID (object ID or player ID)"""
        if hasattr(self.target, 'object_id'):
            return self.target.object_id
        if hasattr(self.target, 'player_id'):
            return self.target.player_id
        return None

    def target_is_player(self) -> bool:
        """Check if target is a player"""
        return hasattr(self.target, 'player_id')

    def target_is_creature(self) -> bool:
        """Check if target is a creature"""
        if hasattr(self.target, 'characteristics'):
            return self.target.characteristics.is_creature()
        return False


@dataclass
class CombatState:
    """
    Complete state of combat at any moment.

    Tracks all attackers, blockers, damage assignments, and
    combat-related flags for the current combat phase.

    Attributes:
        attackers: List of attack declarations
        blockers: List of block declarations
        damage_assignments: List of damage assignments to be dealt
        is_first_strike_step: Whether we're in the first strike damage step
        first_strike_happened: Whether first strike damage has already been dealt
    """
    attackers: List[AttackDeclaration] = field(default_factory=list)
    blockers: List[BlockDeclaration] = field(default_factory=list)
    damage_assignments: List[DamageAssignment] = field(default_factory=list)
    is_first_strike_step: bool = False
    first_strike_happened: bool = False

    # Additional tracking
    blocker_order: Dict[ObjectId, List[Any]] = field(default_factory=dict)
    creatures_that_dealt_damage: Set[ObjectId] = field(default_factory=set)

    def get_attacker_declaration(self, attacker: Any) -> Optional[AttackDeclaration]:
        """Get the attack declaration for a specific attacker"""
        attacker_id = attacker.object_id if hasattr(attacker, 'object_id') else attacker
        for decl in self.attackers:
            if decl.attacker_id == attacker_id:
                return decl
        return None

    def is_blocked(self, attacker: Any) -> bool:
        """Check if an attacker has any blockers assigned"""
        attacker_id = attacker.object_id if hasattr(attacker, 'object_id') else attacker
        return any(b.blocking_id == attacker_id for b in self.blockers if b.is_legal)

    def clear(self):
        """Reset combat state"""
        self.attackers.clear()
        self.blockers.clear()
        self.damage_assignments.clear()
        self.is_first_strike_step = False
        self.first_strike_happened = False
        self.blocker_order.clear()
        self.creatures_that_dealt_damage.clear()


# =============================================================================
# COMBAT RESTRICTION TYPES
# =============================================================================

class CombatRestriction(Enum):
    """Types of combat restrictions"""
    CANNOT_ATTACK = auto()
    CANNOT_ATTACK_ALONE = auto()
    CANNOT_BLOCK = auto()
    CANNOT_BLOCK_ALONE = auto()
    MUST_ATTACK = auto()
    MUST_BLOCK = auto()
    ATTACKS_EACH_TURN_IF_ABLE = auto()


# =============================================================================
# COMBAT MANAGER
# =============================================================================

class CombatManager:
    """
    Manages the entire combat phase (CR 506-511)

    Implements the complete MTG combat phase including:
    - Beginning of Combat step (CR 507)
    - Declare Attackers step (CR 508)
    - Declare Blockers step (CR 509)
    - Combat Damage step (CR 510)
    - End of Combat step (CR 511)

    Handles all combat keywords:
    - First Strike / Double Strike
    - Trample
    - Deathtouch
    - Lifelink
    - Flying / Reach
    - Menace
    - Vigilance
    - Indestructible (via SBA check)

    Attributes:
        game: Reference to the main Game object
        state: Current CombatState tracking all combat information
    """

    def __init__(self, game: 'Game'):
        self.game = game
        self.state = CombatState()

        # Attack/block restrictions tracking
        self._attack_restrictions: Dict[ObjectId, Set[CombatRestriction]] = {}
        self._block_restrictions: Dict[ObjectId, Set[CombatRestriction]] = {}

    # =========================================================================
    # ATTACK METHODS
    # =========================================================================

    def can_attack(self, creature: 'Permanent', defending: Any) -> bool:
        """
        Check if a creature can legally attack a target (CR 508.1a-k)

        A creature can attack if:
        - It's controlled by active player
        - It's untapped (unless it has an ability that allows it)
        - It doesn't have defender
        - It doesn't have summoning sickness (unless haste)
        - It's not subject to "can't attack" effects

        Args:
            creature: The potential attacker
            defending: The player or planeswalker to attack

        Returns:
            True if the creature can legally attack the target
        """
        # Must be a creature
        if not creature.characteristics.is_creature():
            return False

        # Must be controlled by active player
        if creature.controller_id != self.game.active_player_id:
            return False

        # Must be untapped (CR 508.1a)
        if creature.is_tapped:
            return False

        # Cannot have defender (CR 508.1b)
        if self.has_keyword(creature, 'defender'):
            return False

        # Summoning sickness check (CR 508.1c)
        if self._has_summoning_sickness(creature):
            return False

        # Check for "can't attack" restrictions
        creature_id = creature.object_id
        if creature_id in self._attack_restrictions:
            if CombatRestriction.CANNOT_ATTACK in self._attack_restrictions[creature_id]:
                return False

        return True

    def get_attack_requirements(self, creature: 'Permanent') -> List[CombatRestriction]:
        """
        Get all attack requirements for a creature (must attack if able)

        Args:
            creature: The creature to check

        Returns:
            List of CombatRestriction values that require attacking
        """
        requirements = []
        creature_id = creature.object_id

        if creature_id in self._attack_restrictions:
            restrictions = self._attack_restrictions[creature_id]
            if CombatRestriction.MUST_ATTACK in restrictions:
                requirements.append(CombatRestriction.MUST_ATTACK)
            if CombatRestriction.ATTACKS_EACH_TURN_IF_ABLE in restrictions:
                requirements.append(CombatRestriction.ATTACKS_EACH_TURN_IF_ABLE)

        return requirements

    def get_attack_restrictions(self, creature: 'Permanent') -> List[CombatRestriction]:
        """
        Get all attack restrictions for a creature (can't attack)

        Args:
            creature: The creature to check

        Returns:
            List of CombatRestriction values that prevent attacking
        """
        restrictions = []
        creature_id = creature.object_id

        if creature_id in self._attack_restrictions:
            creature_restrictions = self._attack_restrictions[creature_id]
            if CombatRestriction.CANNOT_ATTACK in creature_restrictions:
                restrictions.append(CombatRestriction.CANNOT_ATTACK)
            if CombatRestriction.CANNOT_ATTACK_ALONE in creature_restrictions:
                restrictions.append(CombatRestriction.CANNOT_ATTACK_ALONE)

        # Check for defender keyword
        if self.has_keyword(creature, 'defender'):
            restrictions.append(CombatRestriction.CANNOT_ATTACK)

        return restrictions

    def declare_attackers(self, declarations: List[AttackDeclaration]):
        """
        Process attacker declarations (CR 508.1)

        Args:
            declarations: List of AttackDeclaration objects
        """
        # Validate declarations
        valid_declarations = []
        for decl in declarations:
            if decl.is_legal and self.can_attack(decl.attacker, decl.defending):
                valid_declarations.append(decl)

        # Check "cannot attack alone" restrictions
        if len(valid_declarations) == 1:
            creature = valid_declarations[0].attacker
            creature_id = creature.object_id
            if creature_id in self._attack_restrictions:
                if CombatRestriction.CANNOT_ATTACK_ALONE in self._attack_restrictions[creature_id]:
                    valid_declarations = []

        self.state.attackers = valid_declarations

        # Tap non-vigilant attackers and set attacking flags
        for decl in valid_declarations:
            attacker = decl.attacker

            # Set attacking state
            attacker.is_attacking = True
            if decl.is_attacking_player():
                attacker.attacking_player_id = decl.defending.player_id
            elif decl.is_attacking_planeswalker():
                attacker.attacking_planeswalker_id = decl.defending.object_id

            # Tap unless vigilance (CR 508.1f)
            if not self.has_vigilance(attacker):
                attacker.tap()

            # Initialize blocked_by list
            attacker.blocked_by_ids = []

    # =========================================================================
    # BLOCK METHODS
    # =========================================================================

    def can_block(self, blocker: 'Permanent', attacker: 'Permanent') -> bool:
        """
        Check if a creature can legally block an attacker (CR 509.1a-j)

        Args:
            blocker: The potential blocker
            attacker: The attacking creature

        Returns:
            True if the blocker can legally block the attacker
        """
        # Must be a creature
        if not blocker.characteristics.is_creature():
            return False

        # Must be untapped (CR 509.1a)
        if blocker.is_tapped:
            return False

        # Check for "can't block" restrictions
        blocker_id = blocker.object_id
        if blocker_id in self._block_restrictions:
            if CombatRestriction.CANNOT_BLOCK in self._block_restrictions[blocker_id]:
                return False

        # Evasion checks
        if not self.can_be_blocked_by(attacker, blocker):
            return False

        return True

    def get_block_requirements(self, creature: 'Permanent') -> List[CombatRestriction]:
        """
        Get all block requirements for a creature (must block if able)

        Args:
            creature: The creature to check

        Returns:
            List of CombatRestriction values that require blocking
        """
        requirements = []
        creature_id = creature.object_id

        if creature_id in self._block_restrictions:
            if CombatRestriction.MUST_BLOCK in self._block_restrictions[creature_id]:
                requirements.append(CombatRestriction.MUST_BLOCK)

        return requirements

    def get_block_restrictions(self, creature: 'Permanent') -> List[CombatRestriction]:
        """
        Get all block restrictions for a creature (can't block, menace check)

        Args:
            creature: The creature to check

        Returns:
            List of CombatRestriction values that prevent or restrict blocking
        """
        restrictions = []
        creature_id = creature.object_id

        if creature_id in self._block_restrictions:
            creature_restrictions = self._block_restrictions[creature_id]
            if CombatRestriction.CANNOT_BLOCK in creature_restrictions:
                restrictions.append(CombatRestriction.CANNOT_BLOCK)
            if CombatRestriction.CANNOT_BLOCK_ALONE in creature_restrictions:
                restrictions.append(CombatRestriction.CANNOT_BLOCK_ALONE)

        return restrictions

    def declare_blockers(self, declarations: List[BlockDeclaration]):
        """
        Process blocker declarations (CR 509.1)

        Args:
            declarations: List of BlockDeclaration objects
        """
        # Validate declarations
        valid_declarations = []
        for decl in declarations:
            if decl.is_legal and self.can_block(decl.blocker, decl.blocking):
                valid_declarations.append(decl)

        # Check "cannot block alone" restrictions
        if len(valid_declarations) == 1:
            blocker = valid_declarations[0].blocker
            blocker_id = blocker.object_id
            if blocker_id in self._block_restrictions:
                if CombatRestriction.CANNOT_BLOCK_ALONE in self._block_restrictions[blocker_id]:
                    valid_declarations = []

        self.state.blockers = valid_declarations

        # Validate menace (CR 702.111)
        self._validate_menace_blocks()

        # Set blocking state on blockers and blocked_by on attackers
        for decl in self.state.blockers:
            if decl.is_legal:
                blocker = decl.blocker
                attacker = decl.blocking

                blocker.is_blocking = True
                if not hasattr(blocker, 'blocking_ids'):
                    blocker.blocking_ids = []
                blocker.blocking_ids.append(attacker.object_id)

                if not hasattr(attacker, 'blocked_by_ids'):
                    attacker.blocked_by_ids = []
                attacker.blocked_by_ids.append(blocker.object_id)

    def get_blockers_for(self, attacker: 'Permanent') -> List['Permanent']:
        """
        Get all blockers assigned to an attacker

        Args:
            attacker: The attacking creature

        Returns:
            List of blocking Permanent objects
        """
        attacker_id = attacker.object_id
        blockers = []

        for decl in self.state.blockers:
            if decl.is_legal and decl.blocking_id == attacker_id:
                blockers.append(decl.blocker)

        # Return in damage assignment order if set
        if attacker_id in self.state.blocker_order:
            ordered_blockers = []
            for b in self.state.blocker_order[attacker_id]:
                if b in blockers:
                    ordered_blockers.append(b)
            # Add any blockers not in the order
            for b in blockers:
                if b not in ordered_blockers:
                    ordered_blockers.append(b)
            return ordered_blockers

        return blockers

    def _validate_menace_blocks(self):
        """
        Validate menace blocking requirements (CR 702.111)

        Menace: This creature can't be blocked except by two or more creatures.
        If a menace creature is only blocked by one creature, the block is illegal.
        """
        # Count blockers per attacker
        blocker_counts: Dict[ObjectId, int] = {}
        for decl in self.state.blockers:
            if decl.is_legal:
                attacker_id = decl.blocking_id
                blocker_counts[attacker_id] = blocker_counts.get(attacker_id, 0) + 1

        # Check each attacker with menace
        for attack_decl in self.state.attackers:
            attacker = attack_decl.attacker
            if self.has_keyword(attacker, 'menace'):
                attacker_id = attacker.object_id
                if blocker_counts.get(attacker_id, 0) == 1:
                    # Invalidate the single blocker
                    for block_decl in self.state.blockers:
                        if block_decl.blocking_id == attacker_id:
                            block_decl.is_legal = False

    # =========================================================================
    # DAMAGE METHODS
    # =========================================================================

    def needs_first_strike_step(self) -> bool:
        """
        Check if a first strike damage step is needed (CR 510.5)

        Returns:
            True if any attacking or blocking creature has first strike or double strike
        """
        # Check attackers
        for decl in self.state.attackers:
            if self.applies_first_strike(decl.attacker):
                return True

        # Check blockers
        for decl in self.state.blockers:
            if decl.is_legal and self.applies_first_strike(decl.blocker):
                return True

        return False

    def calculate_combat_damage(self, first_strike_only: bool = False) -> List[DamageAssignment]:
        """
        Calculate all combat damage assignments (CR 510.1)

        Args:
            first_strike_only: If True, only calculate damage from first/double strike creatures

        Returns:
            List of DamageAssignment objects
        """
        assignments = []

        # Calculate attacker damage
        for decl in self.state.attackers:
            attacker = decl.attacker

            # Check if this creature deals damage in this step
            if not self._deals_damage_this_step(attacker, first_strike_only):
                continue

            blockers = self.get_blockers_for(attacker)
            attacker_assignments = self.assign_attacker_damage(
                attacker, blockers, first_strike_only
            )
            assignments.extend(attacker_assignments)

        # Calculate blocker damage
        for decl in self.state.blockers:
            if not decl.is_legal:
                continue

            blocker = decl.blocker
            attacker = decl.blocking

            # Check if this creature deals damage in this step
            if not self._deals_damage_this_step(blocker, first_strike_only):
                continue

            blocker_assignments = self.assign_blocker_damage(
                blocker, [attacker], first_strike_only
            )
            assignments.extend(blocker_assignments)

        return assignments

    def assign_attacker_damage(
        self,
        attacker: 'Permanent',
        blockers: List['Permanent'],
        first_strike: bool = False
    ) -> List[DamageAssignment]:
        """
        Assign damage from an attacking creature (CR 510.1c)

        Args:
            attacker: The attacking creature
            blockers: List of blocking creatures in damage assignment order
            first_strike: Whether this is during the first strike step

        Returns:
            List of DamageAssignment objects
        """
        assignments = []

        power = attacker.effective_power() if hasattr(attacker, 'effective_power') else attacker.characteristics.power or 0
        if power <= 0:
            return assignments

        if not blockers:
            # Unblocked - damage goes to defending player or planeswalker
            decl = self.state.get_attacker_declaration(attacker)
            if decl:
                assignments.append(DamageAssignment(
                    source=attacker,
                    target=decl.defending,
                    amount=power,
                    is_combat=True
                ))
        else:
            # Blocked - assign damage to blockers in order
            remaining = power
            has_deathtouch = self.has_deathtouch(attacker)
            has_trample = self.has_trample(attacker)

            for blocker in blockers:
                if remaining <= 0:
                    break

                lethal = self.get_lethal_damage(blocker, attacker)
                assigned = min(remaining, lethal)

                if assigned > 0:
                    assignments.append(DamageAssignment(
                        source=attacker,
                        target=blocker,
                        amount=assigned,
                        is_combat=True
                    ))
                    remaining -= assigned

            # Trample - excess damage to defended player/planeswalker (CR 702.19)
            if has_trample and remaining > 0:
                decl = self.state.get_attacker_declaration(attacker)
                if decl:
                    assignments.append(DamageAssignment(
                        source=attacker,
                        target=decl.defending,
                        amount=remaining,
                        is_combat=True
                    ))

        return assignments

    def assign_blocker_damage(
        self,
        blocker: 'Permanent',
        attackers: List['Permanent'],
        first_strike: bool = False
    ) -> List[DamageAssignment]:
        """
        Assign damage from a blocking creature (CR 510.1d)

        Args:
            blocker: The blocking creature
            attackers: List of attackers this creature is blocking
            first_strike: Whether this is during the first strike step

        Returns:
            List of DamageAssignment objects
        """
        assignments = []

        power = blocker.effective_power() if hasattr(blocker, 'effective_power') else blocker.characteristics.power or 0
        if power <= 0:
            return assignments

        # In standard combat, a blocker blocks one attacker and deals all damage to it
        for attacker in attackers:
            if power <= 0:
                break
            assignments.append(DamageAssignment(
                source=blocker,
                target=attacker,
                amount=power,
                is_combat=True
            ))
            power = 0  # Blocker deals all damage to first attacker

        return assignments

    def deal_combat_damage(self, assignments: List[DamageAssignment]):
        """
        Deal all assigned combat damage simultaneously (CR 510.2)

        Args:
            assignments: List of DamageAssignment objects to process
        """
        lifelink_gains: Dict[PlayerId, int] = {}

        for assignment in assignments:
            source = assignment.source
            target = assignment.target
            amount = assignment.amount

            if amount <= 0:
                continue

            has_deathtouch = self.has_deathtouch(source)
            has_lifelink = self.has_lifelink(source)
            controller_id = source.controller_id

            # Deal damage to creature
            if assignment.target_is_creature():
                if hasattr(target, 'damage_marked'):
                    target.damage_marked += amount
                else:
                    target.damage_marked = amount

                # Track deathtouch sources
                if has_deathtouch:
                    if not hasattr(target, 'damage_sources_with_deathtouch'):
                        target.damage_sources_with_deathtouch = set()
                    target.damage_sources_with_deathtouch.add(source.object_id)

            # Deal damage to player
            elif assignment.target_is_player():
                if hasattr(target, 'deal_damage'):
                    target.deal_damage(amount, source.object_id)
                elif hasattr(target, 'life'):
                    target.life -= amount

            # Deal damage to planeswalker (remove loyalty counters)
            elif hasattr(target, 'counters'):
                from .types import CounterType
                current_loyalty = target.counters.get(CounterType.LOYALTY, 0)
                target.counters[CounterType.LOYALTY] = max(0, current_loyalty - amount)

            # Track lifelink
            if has_lifelink:
                lifelink_gains[controller_id] = lifelink_gains.get(controller_id, 0) + amount

            # Track that source dealt damage
            self.state.creatures_that_dealt_damage.add(source.object_id)

        # Apply lifelink life gains
        for player_id, amount in lifelink_gains.items():
            player = self.game.get_player(player_id)
            if player:
                if hasattr(player, 'gain_life'):
                    player.gain_life(amount)
                elif hasattr(player, 'life'):
                    player.life += amount

        self.state.damage_assignments = assignments

    def _deals_damage_this_step(self, creature: 'Permanent', first_strike_only: bool) -> bool:
        """
        Determine if a creature deals damage in the current damage step

        Args:
            creature: The creature to check
            first_strike_only: Whether this is the first strike damage step

        Returns:
            True if the creature deals damage in this step
        """
        has_first_strike = self.applies_first_strike(creature)
        has_double_strike = self.applies_double_strike(creature)

        if first_strike_only:
            # Only first strike and double strike deal damage
            return has_first_strike or has_double_strike
        else:
            # Regular damage step
            if self.state.first_strike_happened:
                # Skip creatures with ONLY first strike (not double strike)
                if has_first_strike and not has_double_strike:
                    return False
            return True

    # =========================================================================
    # KEYWORD HANDLING
    # =========================================================================

    def has_evasion(self, creature: 'Permanent') -> Tuple[bool, str]:
        """
        Check if creature has any evasion ability (CR 702)

        Args:
            creature: The creature to check

        Returns:
            Tuple of (has_evasion, evasion_type)
        """
        if self.has_keyword(creature, 'flying'):
            return (True, 'flying')
        if self.has_keyword(creature, 'menace'):
            return (True, 'menace')
        if self.has_keyword(creature, 'shadow'):
            return (True, 'shadow')
        if self.has_keyword(creature, 'horsemanship'):
            return (True, 'horsemanship')
        if self.has_keyword(creature, 'fear'):
            return (True, 'fear')
        if self.has_keyword(creature, 'intimidate'):
            return (True, 'intimidate')
        if self.has_keyword(creature, 'skulk'):
            return (True, 'skulk')
        if self.has_keyword(creature, 'unblockable'):
            return (True, 'unblockable')

        return (False, '')

    def can_be_blocked_by(self, attacker: 'Permanent', blocker: 'Permanent') -> bool:
        """
        Check if an attacker can be blocked by a specific blocker (CR 509)

        Args:
            attacker: The attacking creature
            blocker: The potential blocking creature

        Returns:
            True if the blocker can legally block the attacker
        """
        # Flying check (CR 702.9)
        if self.has_keyword(attacker, 'flying'):
            if not (self.has_keyword(blocker, 'flying') or self.has_keyword(blocker, 'reach')):
                return False

        # Shadow check (CR 702.28)
        if self.has_keyword(attacker, 'shadow'):
            if not self.has_keyword(blocker, 'shadow'):
                return False
        if self.has_keyword(blocker, 'shadow'):
            if not self.has_keyword(attacker, 'shadow'):
                return False

        # Horsemanship check (CR 702.30)
        if self.has_keyword(attacker, 'horsemanship'):
            if not self.has_keyword(blocker, 'horsemanship'):
                return False

        # Fear check (CR 702.36)
        if self.has_keyword(attacker, 'fear'):
            if not (blocker.characteristics.is_artifact() or
                    self._has_color(blocker, 'black')):
                return False

        # Intimidate check (CR 702.13)
        if self.has_keyword(attacker, 'intimidate'):
            if not blocker.characteristics.is_artifact():
                # Check if blocker shares a color with attacker
                if not self._shares_color(attacker, blocker):
                    return False

        # Skulk check (CR 702.118)
        if self.has_keyword(attacker, 'skulk'):
            blocker_power = blocker.effective_power() if hasattr(blocker, 'effective_power') else blocker.characteristics.power or 0
            attacker_power = attacker.effective_power() if hasattr(attacker, 'effective_power') else attacker.characteristics.power or 0
            if blocker_power > attacker_power:
                return False

        # Unblockable
        if self.has_keyword(attacker, 'unblockable'):
            return False

        return True

    def get_lethal_damage(self, creature: 'Permanent', source: 'Permanent') -> int:
        """
        Calculate lethal damage for a creature (CR 510.1c)

        Args:
            creature: The creature receiving damage
            source: The source of the damage

        Returns:
            Amount of damage needed to be lethal (1 if source has deathtouch)
        """
        if self.has_deathtouch(source):
            return 1

        toughness = creature.effective_toughness() if hasattr(creature, 'effective_toughness') else creature.characteristics.toughness or 0
        marked = getattr(creature, 'damage_marked', 0)

        return max(1, toughness - marked)

    def applies_first_strike(self, creature: 'Permanent') -> bool:
        """
        Check if creature has first strike or double strike (CR 702.7)

        Args:
            creature: The creature to check

        Returns:
            True if creature deals damage in the first strike step
        """
        return (self.has_keyword(creature, 'first_strike') or
                self.has_keyword(creature, 'double_strike'))

    def applies_double_strike(self, creature: 'Permanent') -> bool:
        """
        Check if creature has double strike (CR 702.4)

        Args:
            creature: The creature to check

        Returns:
            True if creature has double strike
        """
        return self.has_keyword(creature, 'double_strike')

    def has_trample(self, creature: 'Permanent') -> bool:
        """
        Check if creature has trample (CR 702.19)

        Args:
            creature: The creature to check

        Returns:
            True if creature has trample
        """
        return self.has_keyword(creature, 'trample')

    def has_lifelink(self, creature: 'Permanent') -> bool:
        """
        Check if creature has lifelink (CR 702.15)

        Args:
            creature: The creature to check

        Returns:
            True if creature has lifelink
        """
        return self.has_keyword(creature, 'lifelink')

    def has_vigilance(self, creature: 'Permanent') -> bool:
        """
        Check if creature has vigilance (CR 702.20)

        Args:
            creature: The creature to check

        Returns:
            True if creature has vigilance
        """
        return self.has_keyword(creature, 'vigilance')

    def has_deathtouch(self, creature: 'Permanent') -> bool:
        """
        Check if creature has deathtouch (CR 702.2)

        Args:
            creature: The creature to check

        Returns:
            True if creature has deathtouch
        """
        return self.has_keyword(creature, 'deathtouch')

    def has_keyword(self, creature: 'Permanent', keyword: str) -> bool:
        """
        Check if a creature has a specific keyword ability

        Args:
            creature: The creature to check
            keyword: The keyword to look for (lowercase)

        Returns:
            True if creature has the keyword
        """
        if hasattr(creature, 'has_keyword'):
            return creature.has_keyword(keyword)
        if hasattr(creature, '_keyword_cache'):
            return keyword.lower() in creature._keyword_cache
        return False

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _has_summoning_sickness(self, creature: 'Permanent') -> bool:
        """Check if a creature has summoning sickness"""
        if hasattr(creature, 'has_summoning_sickness'):
            if callable(creature.has_summoning_sickness):
                return creature.has_summoning_sickness()
            return creature.has_summoning_sickness

        if self.has_keyword(creature, 'haste'):
            return False

        return getattr(creature, 'entered_battlefield_this_turn', False)

    def _has_color(self, creature: 'Permanent', color: str) -> bool:
        """Check if a creature has a specific color"""
        if hasattr(creature, 'characteristics'):
            colors = creature.characteristics.get_colors()
            from .objects import Color
            color_map = {
                'white': Color.WHITE,
                'blue': Color.BLUE,
                'black': Color.BLACK,
                'red': Color.RED,
                'green': Color.GREEN
            }
            return color_map.get(color.lower()) in colors
        return False

    def _shares_color(self, creature1: 'Permanent', creature2: 'Permanent') -> bool:
        """Check if two creatures share at least one color"""
        if hasattr(creature1, 'characteristics') and hasattr(creature2, 'characteristics'):
            colors1 = creature1.characteristics.get_colors()
            colors2 = creature2.characteristics.get_colors()
            return bool(colors1 & colors2)
        return False

    def _get_defending_player_id(self) -> PlayerId:
        """Get the defending player ID (opponent of active player)"""
        active = self.game.active_player_id
        for pid in self.game.players:
            if pid != active:
                return pid
        return active

    def reset(self):
        """Reset combat state at end of combat"""
        # Clear combat flags on all creatures
        for perm in self.game.zones.battlefield.creatures():
            perm.is_attacking = False
            perm.is_blocking = False
            if hasattr(perm, 'attacking_player_id'):
                perm.attacking_player_id = None
            if hasattr(perm, 'attacking_planeswalker_id'):
                perm.attacking_planeswalker_id = None
            if hasattr(perm, 'blocked_by_ids'):
                perm.blocked_by_ids.clear()
            if hasattr(perm, 'blocking_ids'):
                perm.blocking_ids.clear()
            if hasattr(perm, 'damage_assignment_order'):
                perm.damage_assignment_order.clear()

        self.state.clear()
        self._attack_restrictions.clear()
        self._block_restrictions.clear()

    def run_combat_phase(self) -> bool:
        """
        Run the complete combat phase.

        This is a wrapper method that calls the standalone run_combat_phase function.

        Returns:
            True if combat occurred (attackers were declared), False otherwise
        """
        return run_combat_phase(self.game)

    def add_attack_restriction(self, creature_id: ObjectId, restriction: CombatRestriction):
        """Add an attack restriction to a creature"""
        if creature_id not in self._attack_restrictions:
            self._attack_restrictions[creature_id] = set()
        self._attack_restrictions[creature_id].add(restriction)

    def add_block_restriction(self, creature_id: ObjectId, restriction: CombatRestriction):
        """Add a block restriction to a creature"""
        if creature_id not in self._block_restrictions:
            self._block_restrictions[creature_id] = set()
        self._block_restrictions[creature_id].add(restriction)

    def remove_restriction(self, creature_id: ObjectId, restriction: CombatRestriction):
        """Remove a combat restriction from a creature"""
        if creature_id in self._attack_restrictions:
            self._attack_restrictions[creature_id].discard(restriction)
        if creature_id in self._block_restrictions:
            self._block_restrictions[creature_id].discard(restriction)


# =============================================================================
# COMBAT PHASE RUNNER
# =============================================================================

def run_combat_phase(game: 'Game') -> bool:
    """
    Orchestrates the complete combat phase (CR 506-511)

    This function runs all steps of the combat phase:
    1. Beginning of combat step (CR 507)
    2. Declare attackers step (CR 508)
    3. Declare blockers step (CR 509)
    4. Combat damage step (CR 510) - may include first strike step
    5. End of combat step (CR 511)

    Args:
        game: The Game object to run combat for

    Returns:
        True if combat occurred (attackers were declared), False otherwise
    """
    from .events import (
        PhaseStartEvent, PhaseEndEvent, StepStartEvent,
        AttacksEvent, BlocksEvent, BecomesBlockedEvent,
        CombatDamageDealtEvent, DamageEvent
    )
    from .types import PhaseType, StepType
    from .sba import run_sba_loop

    combat = game.combat_manager

    # =========================================================================
    # BEGINNING OF COMBAT STEP (CR 507)
    # =========================================================================

    game.current_step = StepType.BEGINNING_OF_COMBAT
    game.events.emit(StepStartEvent(
        step_type=StepType.BEGINNING_OF_COMBAT,
        active_player_id=game.active_player_id
    ))

    # "At the beginning of combat" triggers go on stack here
    # Priority passes
    from .priority import run_priority_round
    run_priority_round(game)
    game._empty_mana_pools()  # CR 106.4b - mana empties at end of each step

    if game.check_game_over():
        combat.reset()
        return False

    # =========================================================================
    # DECLARE ATTACKERS STEP (CR 508)
    # =========================================================================

    game.current_step = StepType.DECLARE_ATTACKERS
    game.events.emit(StepStartEvent(
        step_type=StepType.DECLARE_ATTACKERS,
        active_player_id=game.active_player_id
    ))

    # Active player declares attackers
    active_player = game.get_player(game.active_player_id)
    defending_player_id = combat._get_defending_player_id()
    defending_player = game.get_player(defending_player_id)

    # Get legal attackers
    legal_attackers = []
    for creature in game.zones.battlefield.creatures(game.active_player_id):
        if combat.can_attack(creature, defending_player):
            legal_attackers.append(creature)

    # Get attack declarations from AI or player
    declarations = []
    if hasattr(active_player, 'ai') and active_player.ai:
        # AI chooses attackers using intelligent evaluation
        ai = active_player.ai

        # Build game state for AI decision making
        try:
            from ai.agent import build_game_state, perm_to_info
        except ImportError:
            from ..ai.agent import build_game_state, perm_to_info

        state = build_game_state(game, active_player)

        # Convert legal attackers to PermanentInfo for AI evaluation
        available_attackers = []
        attacker_map = {}  # Map reference to actual permanent
        for creature in legal_attackers:
            info = perm_to_info(creature, game.active_player_id)
            info.reference = creature  # Store reference for later
            available_attackers.append(info)
            attacker_map[id(creature)] = creature

        # Let AI choose which creatures to attack with
        chosen_refs = ai.choose_attackers(state, available_attackers)

        # Convert AI choices back to declarations
        for ref in chosen_refs:
            if ref is not None:
                declarations.append(AttackDeclaration(
                    attacker=ref,
                    defending=defending_player,
                    is_legal=True
                ))

    # Process attack declarations
    if declarations:
        combat.declare_attackers(declarations)

        # Emit attack events
        for decl in combat.state.attackers:
            game.events.emit(AttacksEvent(
                creature=decl.attacker,
                defending=decl.defending
            ))

    # Priority passes
    run_priority_round(game)
    game._empty_mana_pools()  # CR 106.4b - mana empties at end of each step

    if game.check_game_over():
        combat.reset()
        return False

    # If no attackers, skip to end of combat
    if not combat.state.attackers:
        _run_end_of_combat_step(game, combat)
        return False

    # =========================================================================
    # DECLARE BLOCKERS STEP (CR 509)
    # =========================================================================

    game.current_step = StepType.DECLARE_BLOCKERS
    game.events.emit(StepStartEvent(
        step_type=StepType.DECLARE_BLOCKERS,
        active_player_id=game.active_player_id
    ))

    # Defending player declares blockers
    block_declarations = []
    if hasattr(defending_player, 'ai') and defending_player.ai:
        # AI chooses blockers using intelligent evaluation
        ai = defending_player.ai

        # Build game state for AI decision making
        try:
            from ai.agent import build_game_state, perm_to_info
        except ImportError:
            from ..ai.agent import build_game_state, perm_to_info

        state = build_game_state(game, defending_player)

        # Convert attackers to PermanentInfo
        attacker_infos = []
        attacker_map = {}
        for attack_decl in combat.state.attackers:
            attacker = attack_decl.attacker
            info = perm_to_info(attacker, game.active_player_id)
            info.reference = attacker
            attacker_infos.append(info)
            attacker_map[id(attacker)] = attacker

        # Convert available blockers to PermanentInfo
        available_blockers = list(game.zones.battlefield.creatures(defending_player_id))
        blocker_infos = []
        blocker_map = {}
        for blocker in available_blockers:
            if any(combat.can_block(blocker, ad.attacker) for ad in combat.state.attackers):
                info = perm_to_info(blocker, defending_player_id)
                info.reference = blocker
                blocker_infos.append(info)
                blocker_map[id(blocker)] = blocker

        # Let AI choose blocking assignments
        block_assignments = ai.choose_blockers(state, attacker_infos, blocker_infos)

        # Convert AI choices back to declarations
        for attacker_ref, blocker_refs in block_assignments.items():
            for blocker_ref in blocker_refs:
                if attacker_ref is not None and blocker_ref is not None:
                    # Verify the block is legal
                    if combat.can_block(blocker_ref, attacker_ref):
                        block_declarations.append(BlockDeclaration(
                            blocker=blocker_ref,
                            blocking=attacker_ref,
                            is_legal=True
                        ))

    # Process block declarations
    if block_declarations:
        combat.declare_blockers(block_declarations)

        # Emit block and becomes blocked events
        for decl in combat.state.blockers:
            if decl.is_legal:
                game.events.emit(BlocksEvent(
                    blocker=decl.blocker,
                    attacker=decl.blocking
                ))

        # Emit becomes blocked events
        for attack_decl in combat.state.attackers:
            blockers = combat.get_blockers_for(attack_decl.attacker)
            if blockers:
                game.events.emit(BecomesBlockedEvent(
                    attacker_id=attack_decl.attacker_id,
                    blocker_ids=[b.object_id for b in blockers]
                ))

    # Attacking player orders blockers for each attacker with multiple blockers
    for attack_decl in combat.state.attackers:
        blockers = combat.get_blockers_for(attack_decl.attacker)
        if len(blockers) > 1:
            # For now, keep default order (AI would choose order here)
            combat.state.blocker_order[attack_decl.attacker_id] = blockers

    # Priority passes
    run_priority_round(game)
    game._empty_mana_pools()  # CR 106.4b - mana empties at end of each step

    if game.check_game_over():
        combat.reset()
        return False

    # =========================================================================
    # COMBAT DAMAGE STEP (CR 510)
    # =========================================================================

    # Check if first strike damage step is needed
    if combat.needs_first_strike_step():
        # FIRST STRIKE DAMAGE STEP
        game.current_step = StepType.FIRST_STRIKE_DAMAGE
        combat.state.is_first_strike_step = True

        game.events.emit(StepStartEvent(
            step_type=StepType.FIRST_STRIKE_DAMAGE,
            active_player_id=game.active_player_id
        ))

        # Calculate and deal first strike damage
        first_strike_assignments = combat.calculate_combat_damage(first_strike_only=True)
        if first_strike_assignments:
            combat.deal_combat_damage(first_strike_assignments)

            # Emit damage events
            damage_events = []
            for assignment in first_strike_assignments:
                damage_events.append(DamageEvent(
                    source=assignment.source,
                    target=assignment.target,
                    amount=assignment.amount,
                    is_combat=True
                ))

            game.events.emit(CombatDamageDealtEvent(
                is_first_strike=True,
                damage_events=damage_events,
                attacking_player_id=game.active_player_id
            ))

        combat.state.first_strike_happened = True

        # Run SBAs (creatures may die)
        run_sba_loop(game)

        # Priority passes
        run_priority_round(game)
        game._empty_mana_pools()  # CR 106.4b - mana empties at end of each step

        if game.check_game_over():
            combat.reset()
            return True

    # REGULAR COMBAT DAMAGE STEP
    game.current_step = StepType.COMBAT_DAMAGE
    combat.state.is_first_strike_step = False

    game.events.emit(StepStartEvent(
        step_type=StepType.COMBAT_DAMAGE,
        active_player_id=game.active_player_id
    ))

    # Calculate and deal regular damage
    regular_assignments = combat.calculate_combat_damage(first_strike_only=False)
    if regular_assignments:
        combat.deal_combat_damage(regular_assignments)

        # Emit damage events
        damage_events = []
        for assignment in regular_assignments:
            damage_events.append(DamageEvent(
                source=assignment.source,
                target=assignment.target,
                amount=assignment.amount,
                is_combat=True
            ))

        game.events.emit(CombatDamageDealtEvent(
            is_first_strike=False,
            damage_events=damage_events,
            attacking_player_id=game.active_player_id
        ))

    # Run SBAs
    run_sba_loop(game)

    # Priority passes
    run_priority_round(game)
    game._empty_mana_pools()  # CR 106.4b - mana empties at end of each step

    if game.check_game_over():
        combat.reset()
        return True

    # =========================================================================
    # END OF COMBAT STEP (CR 511)
    # =========================================================================

    _run_end_of_combat_step(game, combat)

    return True


def _run_end_of_combat_step(game: 'Game', combat: CombatManager):
    """
    Run the end of combat step (CR 511)

    Args:
        game: The Game object
        combat: The CombatManager
    """
    from .events import StepStartEvent
    from .types import StepType
    from .priority import run_priority_round

    game.current_step = StepType.END_OF_COMBAT
    game.events.emit(StepStartEvent(
        step_type=StepType.END_OF_COMBAT,
        active_player_id=game.active_player_id
    ))

    # "At end of combat" triggers go on stack here
    # Priority passes
    run_priority_round(game)
    game._empty_mana_pools()  # CR 106.4b - mana empties at end of each step

    # Remove creatures from combat (CR 511.3)
    combat.reset()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def calculate_combat_outcome(
    attacker: 'Permanent',
    blockers: List['Permanent'],
    combat_manager: Optional[CombatManager] = None
) -> Dict[str, Any]:
    """
    Calculate the predicted outcome of a combat engagement

    Args:
        attacker: The attacking creature
        blockers: List of blocking creatures
        combat_manager: Optional CombatManager for keyword checks

    Returns:
        Dict with:
        - 'attacker_survives': bool
        - 'blockers_that_die': List of blocker references
        - 'damage_to_player': int (if trample or unblocked)
    """
    result = {
        'attacker_survives': True,
        'blockers_that_die': [],
        'damage_to_player': 0
    }

    attacker_power = attacker.effective_power() if hasattr(attacker, 'effective_power') else attacker.characteristics.power or 0
    attacker_toughness = attacker.effective_toughness() if hasattr(attacker, 'effective_toughness') else attacker.characteristics.toughness or 0

    has_deathtouch = False
    has_trample = False
    has_indestructible = False

    if combat_manager:
        has_deathtouch = combat_manager.has_deathtouch(attacker)
        has_trample = combat_manager.has_trample(attacker)
        has_indestructible = combat_manager.has_keyword(attacker, 'indestructible')

    if not blockers:
        result['damage_to_player'] = attacker_power
        return result

    # Calculate damage to attacker
    total_damage_to_attacker = 0
    blocker_has_deathtouch = False

    for blocker in blockers:
        blocker_power = blocker.effective_power() if hasattr(blocker, 'effective_power') else blocker.characteristics.power or 0
        total_damage_to_attacker += blocker_power

        if combat_manager and combat_manager.has_deathtouch(blocker):
            blocker_has_deathtouch = True

    # Check if attacker survives
    if not has_indestructible:
        if blocker_has_deathtouch and total_damage_to_attacker > 0:
            result['attacker_survives'] = False
        elif total_damage_to_attacker >= attacker_toughness:
            result['attacker_survives'] = False

    # Calculate damage to blockers
    remaining_damage = attacker_power
    for blocker in blockers:
        if remaining_damage <= 0:
            break

        blocker_toughness = blocker.effective_toughness() if hasattr(blocker, 'effective_toughness') else blocker.characteristics.toughness or 0
        blocker_indestructible = combat_manager and combat_manager.has_keyword(blocker, 'indestructible')

        if has_deathtouch:
            lethal = 1
        else:
            lethal = blocker_toughness

        assigned = min(remaining_damage, lethal)

        if not blocker_indestructible:
            if has_deathtouch and assigned > 0:
                result['blockers_that_die'].append(blocker)
            elif assigned >= blocker_toughness:
                result['blockers_that_die'].append(blocker)

        remaining_damage -= assigned

    # Trample damage
    if has_trample and remaining_damage > 0:
        result['damage_to_player'] = remaining_damage

    return result


def get_optimal_blocks(
    attackers: List['Permanent'],
    available_blockers: List['Permanent'],
    combat_manager: Optional[CombatManager] = None
) -> List[BlockDeclaration]:
    """
    Calculate optimal blocking assignments (simple heuristic)

    This is a basic implementation that prioritizes:
    1. Blocking creatures that would deal lethal damage
    2. Trading favorably when possible
    3. Chump blocking as a last resort

    Args:
        attackers: List of attacking creatures
        available_blockers: List of available blocking creatures
        combat_manager: Optional CombatManager for keyword and legality checks

    Returns:
        List of BlockDeclaration objects
    """
    declarations = []
    remaining_blockers = list(available_blockers)

    # Sort attackers by power (block biggest threats first)
    sorted_attackers = sorted(
        attackers,
        key=lambda a: a.effective_power() if hasattr(a, 'effective_power') else a.characteristics.power or 0,
        reverse=True
    )

    for attacker in sorted_attackers:
        if not remaining_blockers:
            break

        best_blocker = None
        best_score = -float('inf')

        for blocker in remaining_blockers:
            # Check if block is legal
            if combat_manager and not combat_manager.can_block(blocker, attacker):
                continue

            # Calculate score for this block
            score = _calculate_block_score(attacker, blocker, combat_manager)

            if score > best_score:
                best_score = score
                best_blocker = blocker

        if best_blocker and best_score > 0:  # Only block if beneficial
            declarations.append(BlockDeclaration(
                blocker=best_blocker,
                blocking=attacker,
                is_legal=True
            ))
            remaining_blockers.remove(best_blocker)

    return declarations


def _calculate_block_score(
    attacker: 'Permanent',
    blocker: 'Permanent',
    combat_manager: Optional[CombatManager]
) -> float:
    """
    Calculate a score for how good a block assignment is

    Higher score = better block
    """
    attacker_power = attacker.effective_power() if hasattr(attacker, 'effective_power') else attacker.characteristics.power or 0
    attacker_toughness = attacker.effective_toughness() if hasattr(attacker, 'effective_toughness') else attacker.characteristics.toughness or 0
    blocker_power = blocker.effective_power() if hasattr(blocker, 'effective_power') else blocker.characteristics.power or 0
    blocker_toughness = blocker.effective_toughness() if hasattr(blocker, 'effective_toughness') else blocker.characteristics.toughness or 0

    attacker_deathtouch = combat_manager and combat_manager.has_deathtouch(attacker)
    blocker_deathtouch = combat_manager and combat_manager.has_deathtouch(blocker)
    attacker_first_strike = combat_manager and combat_manager.applies_first_strike(attacker)
    blocker_first_strike = combat_manager and combat_manager.applies_first_strike(blocker)
    blocker_indestructible = combat_manager and combat_manager.has_keyword(blocker, 'indestructible')

    # Calculate outcomes
    blocker_kills_attacker = blocker_power >= attacker_toughness or blocker_deathtouch
    attacker_kills_blocker = (attacker_power >= blocker_toughness or attacker_deathtouch) and not blocker_indestructible

    # First strike considerations
    if attacker_first_strike and not blocker_first_strike:
        if attacker_kills_blocker:
            blocker_kills_attacker = False  # Blocker dies before dealing damage

    score = 0.0

    # Favorable trade: we kill attacker and survive
    if blocker_kills_attacker and not attacker_kills_blocker:
        score = 100 + attacker_power  # Bonus for killing larger creatures

    # Even trade: both die
    elif blocker_kills_attacker and attacker_kills_blocker:
        # Trade up = positive, trade down = negative
        score = 50 + (attacker_power - blocker_power)

    # Chump block: we die, they survive
    elif attacker_kills_blocker and not blocker_kills_attacker:
        # Only worth it if we're blocking something big
        if attacker_power >= 3:
            score = 10 + (attacker_power - blocker_power)
        else:
            score = -10  # Not worth chumping small creatures

    # Stalemate: neither dies
    else:
        score = 25  # Preventing damage is good

    return score


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Data classes
    'AttackDeclaration',
    'BlockDeclaration',
    'DamageAssignment',
    'CombatState',
    'CombatRestriction',

    # Main class
    'CombatManager',

    # Phase runner
    'run_combat_phase',

    # Utility functions
    'calculate_combat_outcome',
    'get_optimal_blocks',
]
