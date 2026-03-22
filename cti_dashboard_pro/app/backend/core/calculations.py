import math
from .psychro_engine import psychrometrics, init_psychro_engine
from .merkel_engine import merkel_kavl, init_merkel_engine

def init(psychro_lib_path="data/psychro_f_alt.bin", merkel_lib_path="data/merkel_poly.bin"):
    init_psychro_engine(psychro_lib_path)
    init_merkel_engine(merkel_lib_path)

def get_psychrometric_props(twb):
    try:
        props = psychrometrics(twb, twb)
        return {"ws": props["HR"], "hs": props["H"], "pws": props["P"]}
    except Exception:
        return {"ws": 0, "hs": 0, "pws": 0}

def calculate_demand_kavl(twb, hwt, cwt, lg_ratio):
    try:
        result = merkel_kavl(hwt, cwt, twb, lg_ratio)
        if result and result.get("valid"):
            return result["kavl"]
        return float('nan')
    except Exception:
        return float('nan')

def calculate_supply_kavl(lg_ratio, constant_c, constant_m):
    return constant_c * math.pow(lg_ratio, -constant_m)

def find_cwt(inputs, wbt, range_percent, flow_percent):
    design_range = inputs["designHWT"] - inputs["designCWT"]
    actual_range = design_range * range_percent / 100.0
    actual_lg = inputs["lgRatio"] * (flow_percent / 100.0)

    supply_kavl = calculate_supply_kavl(actual_lg, inputs["constantC"], inputs["constantM"])

    best_cwt = wbt + 1
    min_diff = float('inf')
    low_approach = 0.01
    high_approach = 80.0
    tolerance = 1e-7

    for _ in range(100):
        mid_approach = (low_approach + high_approach) / 2.0
        cwt_guess = wbt + mid_approach
        hwt = cwt_guess + actual_range

        try:
            demand_kavl = calculate_demand_kavl(wbt, hwt, cwt_guess, actual_lg)
        except Exception:
            demand_kavl = float('nan')

        if math.isnan(demand_kavl) or demand_kavl <= 0:
            low_approach = mid_approach
            continue

        diff = demand_kavl - supply_kavl
        abs_diff = abs(diff)

        if abs_diff < min_diff:
            min_diff = abs_diff
            best_cwt = cwt_guess

        if abs_diff < tolerance:
            break

        if diff > 0:
            low_approach = mid_approach
        else:
            high_approach = mid_approach

    return best_cwt

def solve_off_design_cwt(wbt, range_val, lg, const_c, const_m):
    supply_kavl = calculate_supply_kavl(lg, const_c, const_m)
    if math.isnan(supply_kavl) or supply_kavl <= 0:
        return None

    low_approach = 0.01
    high_approach = 80.0
    best_cwt = float('nan')
    best_diff = float('inf')
    matched_demand = float('nan')
    tolerance = 1e-7
    max_iters = 100

    for _ in range(max_iters):
        mid_approach = (low_approach + high_approach) / 2.0
        guess_cwt = wbt + mid_approach
        guess_hwt = guess_cwt + range_val

        try:
            demand_kavl = calculate_demand_kavl(wbt, guess_hwt, guess_cwt, lg)
        except Exception:
            demand_kavl = float('nan')

        if math.isnan(demand_kavl) or demand_kavl <= 0:
            low_approach = mid_approach
            continue

        diff = demand_kavl - supply_kavl
        abs_diff = abs(diff)

        if abs_diff < best_diff:
            best_diff = abs_diff
            best_cwt = guess_cwt
            matched_demand = demand_kavl

        if abs_diff < tolerance:
            break

        if diff > 0:
            low_approach = mid_approach
        else:
            high_approach = mid_approach

    if math.isnan(best_cwt) or best_diff > 0.5:
        return None

    return {
        "cwt": best_cwt,
        "approach": best_cwt - wbt,
        "hwt": best_cwt + range_val,
        "demandKavl": matched_demand,
        "supplyKavl": supply_kavl
    }
