# FLEX

## Overview

FLEX is a modeling suite for households' behavior, energy system operation, and interaction in the energy community.
It is developed by 
[Fraunhofer ISI](https://www.isi.fraunhofer.de/) and 
[TU Wien (Energy Economics Group)](https://eeg.tuwien.ac.at/)
in the framework of the H2020 project [newTRENDs](https://newTRENDs2020.eu/).

**FLEX contains three modules:**

First is `FLEX-Behavior`, which models the energy-related behavior of a specified household. 
For each individual household member, the activity profile is modeled at a 10-minute resolution based on a Markov chain model. 
Then, the activity profile is converted to the profiles of appliance electricity and hot water demand, as well as building occupancy. 
Finally, household members' profiles are aggregated to the household level in hourly resolution.

Second is `FLEX-Operation`, which focuses on the operation of the household's energy system. 
Taking the results from `FLEX-Behavior`, `FLEX-Operation` is further configured with the household’s building envelope and technology system, 
including the heating system, PV, thermal and battery storage, and EV. The model calculates the system operation in hourly resolution, 
as well as the energy consumption and cost. It can run in both simulation and optimization modes, with the latter minimizing the energy cost and representing the use of SEMS. 

Third is `FLEX-Community`, which takes a group of households' results from `FLEX-Operation` as input and models the operation of an energy community from an aggregator's perspective. 
The aggregator can make a profit by using the following options: 
(1) Facilitate the peer-to-peer (P2P) electricity trading among the households in real-time, and 
(2) Optimize the operation of the batteries of its own or community members to buy at lower prices and sell at higher. 

## Getting started <div id="Getting_started"/>

To work with FLEX, please first follow the steps for installation 

1. Clone the repo to your local computer;
2. Open the project and install the requirements with `pip install -r requirements.txt` in the terminal;
3. Install a solver for the `FLEX-Operation` model (setup with [Pyomo](http://www.pyomo.org/)). 
We suggest to use [gurobi](https://www.gurobi.com/), and if you would like to try other solvers, 
we appreciate if you could inform us the experience. 
In the `model_opt.py` file, you can switch to others solvers in `pyo.SolverFactory("gurobi")`.

In the "tests" folder, we created three examples using the three FLEX models. 
They are good starting points for you to understand how to use the models.

## Citation

In the "doc" folder, you can find the working paper that comprehensively introduces the FLEX modeling suite. 
Until it is published, we suggest to use the following citation:

> Yu, S.; Mascherbauer, P.; Haupt, T.; Skrona, K.; Rickmann, H.; Kochański, M.; Kranzl, L.; (2024). 
Modeling households’ behavior, energy system operation, andinteraction in the energy community. doi: 10.2139/ssrn.4992581

## Lisence

As mentioned, FLEX is developed by 
[Fraunhofer ISI](https://www.isi.fraunhofer.de/) and 
[TU Wien (Energy Economics Group)](https://eeg.tuwien.ac.at/)
in the framework of the H2020 project [newTRENDs](https://newTRENDs2020.eu/).
The developers (2021-2023) include:
* [Songmin Yu](https://www.isi.fraunhofer.de/en/competence-center/energiepolitik-energiemaerkte/mitarbeiter/yu.html): songmin.yu@isi.fraunhofer.de
* [Philipp Mascherbauer](https://eeg.tuwien.ac.at/staff/people/philipp-mascherbauer): philipp.mascherbauer@tuwien.ac.at
* [Thomas Haupt](https://www.hs-ansbach.de/personen/haupt-thomas/): thomas.haupt@hs-ansbach.de
* Kevan Skrona: kevan.skorna@gmail.com
* Hannah Rickmann: rickmann99@web.de

FLEX is licensed under the open source [MIT License](https://github.com/H2020-newTRENDs/FLEX/blob/master/LICENSE.txt).

