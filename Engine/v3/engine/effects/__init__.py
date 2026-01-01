"""Effect system - triggered, activated, continuous, replacement"""
from .triggered import TriggeredAbility, TriggerManager, TriggerCondition
from .activated import ActivatedAbility, ManaAbility, LoyaltyAbility
from .continuous import ContinuousEffect, StaticAbility, Duration
from .replacement import ReplacementEffect, PreventionEffect
from .layers import LayerSystem, Layer
