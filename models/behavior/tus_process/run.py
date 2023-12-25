from models.behavior.tus_process.source.markov_model import MarkovActivityProfileGenerator
from models.behavior.tus_process.source.tus_processor import TUSActivityProfileProcessor
from models.behavior.tus_process.source.activity_start import calc_starting_activity


def process_tou_activity_profile():
    tapp = TUSActivityProfileProcessor()
    tapp.generate_input_activity_profile()


def gen_markov_matrix():
    model = MarkovActivityProfileGenerator()
    model.generate_activity_change_prob_matrix()
    model.generate_activity_duration_prob_matrix()


if __name__ == "__main__":
    # process_tou_activity_profile()
    # gen_markov_matrix()
    calc_starting_activity()
