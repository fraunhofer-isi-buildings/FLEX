from typing import TYPE_CHECKING
import random
if TYPE_CHECKING:
    from models.behavior.scenario import BehaviorScenario

from models.behavior.scenario import BehaviorScenario
from utils.func import day2weekday


class Person:
    def __init__(self, scenario: "BehaviorScenario", id_person_type: int, id_teleworking_type: int):
        self.scenario = scenario
        self.id_person_type = id_person_type
        self.id_teleworking_type = id_teleworking_type
        self.timeslot_num = 144
        self.activity_profile = []
        self.technology_profile = []
        self.appliance_electricity_demand = []
        self.hot_water_demand = []
        self.location = []

    def setup(self):
        self.setup_activity_profile()
        self.setup_location_profile()
        self.setup_electricity_and_hotwater_demand_profile()

    def replace_activity_working(self, id_day_type: int, timeslot: int):
        # The model may select "working" for student or retired adult because they are lack of data and
        # when estimating the Markov parameters, we used "ordered dict" to filter the dataframe.
        # So here, if person_type in [3, 4] meaning student or retired adult,
        # the working activity is replaced with most common activity in that timeslot according to the raw TUS data.
        return self.scenario.get_period_most_common_activity(
            id_person_type=self.id_person_type,
            id_day_type=id_day_type,
            timeslot=timeslot
        )

    def setup_activity_profile(self):
        activities = []
        for day in range(1, 366):
            week_day, id_day_type = day2weekday(day)
            id_activity_start = self.scenario.get_activity_start(
                id_person_type=self.id_person_type,
                id_day_type=id_day_type
            )
            if self.id_person_type in [3, 4] and id_activity_start == 11:
                id_activity_start = self.replace_activity_working(
                    id_day_type=id_day_type,
                    timeslot=1
                )
            activity_duration_start = self.scenario.get_activity_duration(
                id_person_type=self.id_person_type,
                id_day_type=id_day_type,
                id_activity=id_activity_start,
                timeslot=1
            )
            day_activities = [id_activity_start] * activity_duration_start
            timeslot = activity_duration_start + 1
            while timeslot < 145:
                id_activity_before = day_activities[-1]
                id_activity_now = self.scenario.get_activity_now(
                    self.id_person_type,
                    id_day_type,
                    id_activity_before,
                    timeslot
                )
                if self.id_person_type in [3, 4] and id_activity_now == 11:
                    id_activity_now = self.replace_activity_working(
                        id_day_type=id_day_type,
                        timeslot=timeslot
                    )
                duration = self.scenario.get_activity_duration(
                    self.id_person_type,
                    id_day_type,
                    id_activity_now,
                    timeslot
                )
                day_activities += [id_activity_now] * duration
                timeslot = len(day_activities)
            activities += day_activities[0:144]
        self.activity_profile = activities

    def setup_location_profile(self):
        for index, activity_id in enumerate(self.activity_profile):
            if index % 24 == 0:  # start of new day
                wfh_prob = self.scenario.teleworking_prob[self.id_teleworking_type]
                work_location = 1 if random.uniform(0, 1) < wfh_prob else 0
            activity_location = self.scenario.activity_location[activity_id]
            if activity_location == 2:
                if activity_id == 11:  # id_activity = 11 --> working
                    activity_location = work_location
                else:
                    activity_location = 0 if random.uniform(0, 1) <= 0.5 else 1
            self.location.append(activity_location)

    def setup_electricity_and_hotwater_demand_profile(self):
        self.appliance_electricity_demand = [0] * len(self.activity_profile)
        self.hot_water_demand = [0] * len(self.activity_profile)

        for timeslot, id_activity in enumerate(self.activity_profile):
            id_technology = self.scenario.get_activity_technology(id_activity)
            self.technology_profile.append(id_technology)
            technology_power = self.scenario.get_technology_power(id_technology)
            tec_duration = self.scenario.get_technology_duration(id_technology)
            if timeslot + tec_duration > len(self.activity_profile):
                # duration of technology ends with end of day (if longer)
                tec_duration = len(self.activity_profile) - timeslot

            if tec_duration > 1 and id_technology == self.technology_profile[-2]:
                technology_power = 0
            elif tec_duration < 1:
                technology_power = technology_power * tec_duration
                tec_duration = 1
            else:
                pass

            for idx in range(int(tec_duration)):
                if id_technology == 23:  # hot water was triggered
                    self.hot_water_demand[timeslot + idx] += technology_power
                else:
                    self.appliance_electricity_demand[timeslot + idx] += technology_power

        for index, location in enumerate(self.location):
            if location == 0:
                self.hot_water_demand[index] = 0
                self.appliance_electricity_demand[index] = 0
