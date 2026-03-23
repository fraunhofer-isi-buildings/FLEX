# Overview

## Background

FLEX was originally developed as part of the EU H2020 project [newTRENDs](https://newTRENDs2020.eu/), a collaboration between [Fraunhofer ISI](https://www.isi.fraunhofer.de/) and [TU Wien (Energy Economics Group)](https://eeg.tuwien.ac.at/). The goal was to model how households behave, how their energy systems operate, and how groups of households can interact within an energy community.

This repository is a fork of the [original FLEX project](https://github.com/H2020-newTRENDs/FLEX), maintained by the **Climate-Neutral Buildings** group at Fraunhofer ISI for continued research and method development.

## What FLEX Models

FLEX addresses three levels of analysis, implemented as three sequentially coupled modules:

### FLEX-Behavior

Models the **demand side**: what do household members do throughout the day, and how does that translate into energy demand?

The key research question is: how does occupant behavior — activity patterns, appliance use, hot water consumption, occupancy — vary across different household types, and how does this affect the load profiles that downstream energy models need as input? Rather than using static load profiles, FLEX-Behavior generates stochastic, behavior-derived demand profiles.

### FLEX-Operation

Models the **supply and dispatch side**: given a household's technology stack (heat pump, PV, battery, EV, etc.) and the demand from FLEX-Behavior, what is the optimal or reference operation of the energy system?

The key distinction here is between two operating modes:
* **Reference mode** — no smart control, devices operate by simple rules (heat when needed, charge EV when at home).
* **Optimization mode** — a Smart Energy Management System (SEMS) minimizes the household's electricity cost by optimally scheduling flexible devices.

This makes FLEX-Operation a direct tool for quantifying the value of demand flexibility and SEMS at the household level.

### FLEX-Community

Models the **community level**: given a group of households' operation results, how can an energy community aggregator generate profit?

Two mechanisms are analyzed:
* **Peer-to-peer (P2P) trading** — surplus PV generation from one household is consumed by a neighbor rather than being fed to the grid, with the aggregator facilitating and profiting from the spread.
* **Aggregator battery optimization** — the aggregator operates a community battery (or controls household batteries) to buy electricity cheaply and sell at higher prices.

## License

MIT License — see `LICENSE` in the repository root.

## Citation

If you use FLEX in research, please cite:

> Yu, S.; Mascherbauer, P.; Haupt, T.; Skrona, K.; Rickmann, H.; Kochański, M.; Kranzl, L. (2025). Modeling households' behavior, energy system operation, and interaction in the energy community. *Energy*, p. 136338. doi: [10.1016/j.energy.2025.136338](https://www.sciencedirect.com/science/article/pii/S0360544225019802)
