from enum import Enum, auto


class InputTables(Enum):
    # FLEX-Behavior
    BehaviorScenario_Household = auto()
    BehaviorScenario_Person = auto()
    BehaviorID_Activity = auto()
    BehaviorID_PersonType = auto()
    BehaviorID_DayType = auto()
    BehaviorID_Location = auto()
    BehaviorID_Technology = auto()
    BehaviorID_TeleworkingType = auto()
    BehaviorParam_TeleworkingProb = auto()
    BehaviorParam_Activity_TUSProfile = auto()
    BehaviorParam_Activity_TUSStart = auto()
    BehaviorParam_Activity_ChangeProb = auto()
    BehaviorParam_Activity_DurationProb = auto()
    BehaviorParam_Activity_Location = auto()
    BehaviorParam_Technology_Power = auto()
    BehaviorParam_Technology_Duration = auto()
    BehaviorParam_Technology_TriggerProbability = auto()

    # FLEX-Operation
    OperationScenario = auto()
    OperationScenario_Component_Battery = auto()
    OperationScenario_Component_Behavior = auto()
    OperationScenario_Component_Boiler = auto()
    OperationScenario_Component_Building = auto()
    OperationScenario_Component_EnergyPrice = auto()
    OperationScenario_Component_HeatingElement = auto()
    OperationScenario_Component_HotWaterTank = auto()
    OperationScenario_Component_PV = auto()
    OperationScenario_Component_Region = auto()
    OperationScenario_Component_SpaceCoolingTechnology = auto()
    OperationScenario_Component_SpaceHeatingTank = auto()
    OperationScenario_Component_Vehicle = auto()
    OperationScenario_BehaviorProfile = auto()
    OperationScenario_DrivingProfile_ParkingHome = auto()
    OperationScenario_DrivingProfile_Distance = auto()
    OperationScenario_EnergyPrice = auto()
    OperationScenario_RegionWeather = auto()

    # FLEX-Community
    CommunityScenario = auto()
    CommunityScenario_EnergyPrice = auto()
    CommunityScenario_OperationScenario = auto()
    CommunityScenario_Household_RefHour = auto()
    CommunityScenario_Household_RefYear = auto()
    CommunityScenario_Component_Battery = auto()


class OutputTables(Enum):
    # FLEX-Behavior
    BehaviorResult_PersonProfiles = auto()
    BehaviorResult_HouseholdProfiles = auto()
    # FLEX-Operation
    OperationResult_OptHour = auto()
    OperationResult_OptMonth = auto()
    OperationResult_OptYear = auto()
    OperationResult_RefHour = auto()
    OperationResult_RefMonth = auto()
    OperationResult_RefYear = auto()
    OperationResult_EnergyCost = auto()
    OperationResult_EnergyCostChange = auto()
    # FLEX-Community
    CommunityResult_AggregatorHour = auto()
    CommunityResult_AggregatorYear = auto()
