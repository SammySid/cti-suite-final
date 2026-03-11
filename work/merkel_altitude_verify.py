"""
MERKEL ALTITUDE VERIFICATION — JS Engine vs CTI GUI
====================================================
Opens CTI Toolkit in Merkel mode, sweeps altitude and temperature
combinations, and compares the GUI's KaV/L values against what the
JS engine (merkel-engine.js) would produce — implemented here in
Python to allow batch comparison.

Tests TWO hypotheses for altitude handling:
  H1 (current JS): alt_m → alt_ft = alt_m/0.3048 → x = alt_ft/10000
  H2 (no feet):    alt_m → x = alt_m/10000  (meters passed directly)

Reports which hypothesis matches the CTI GUI, and shows full discrepancy
table across all temperature ranges and altitudes.

Usage:
    cd "cti-suite-final"
    python work/merkel_altitude_verify.py
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'important'))

from Merkel_Siphon import MerkelSiphon

# ============================================================
# MERKEL ENGINE — Python port of merkel-engine.js
# ============================================================

P_SEA_LEVEL_PSI = 14.696
CHEBYSHEV_POINTS = [0.9, 0.6, 0.4, 0.1]
CP_DRY_AIR_BTU  = 0.24
H_FG_BTU        = 1061.0
CP_STEAM_BTU    = 0.444

# ln(f*Pws) lookup table (301 pts, 50–200°F, 0.5°F step)
# from merkel-engine.js LN_FPWS_TABLE
LN_FPWS_TABLE = [
  -1.72142105930212952,-1.70282952597788917,-1.68427894942444700,-1.66576920332498180,
  -1.64730016183810246,-1.62887169959610634,-1.61048369170324723,-1.59213601373399483,
  -1.57382854173134445,-1.55556115220513513,-1.53733372213034603,-1.51914612894544754,
  -1.50099825055075420,-1.48288996530673911,-1.46482115203248320,-1.44679169000399099,
  -1.42880145895261146,-1.41085033906347279,-1.39293821097387083,-1.37506495577171939,
  -1.35723045499401263,-1.33943459062524561,-1.32167724509593487,-1.30395830128107093,
  -1.28627764249860421,-1.26863515250800707,-1.25103071550872813,-1.23346421613878698,
  -1.21593553947324340,-1.19844457102283575,-1.18099119673248421,-1.16357530297990519,
  -1.14619677657418317,-1.12885550475436514,-1.11155137518809344,-1.09428427597022937,
  -1.07705409562146315,-1.05986072308698764,-1.04270404773511349,-1.02558395935599922,
  -1.00850034816026857,-0.99145310477774851,-0.97444212025611365,-0.95746728605963616,
  -0.94052849406791605,-0.92362563657456997,-0.90675860628600879,-0.88992729632016510,
  -0.87313160020527580,-0.85637141187861732,-0.83964662568534609,-0.82295713637723189,
  -0.80630283911150802,-0.78968362944963633,-0.77309940335615246,-0.75655005719752755,
  -0.74003548774093120,-0.72355559215317156,-0.70711026799948118,-0.69069941324243345,
  -0.67432292624081436,-0.65798070574847445,-0.64167265091327841,-0.62539866127597321,
  -0.60915863676913251,-0.59295247771606141,-0.57678008482973164,-0.56064135921172964,
  -0.54453620235122735,-0.52846451612388901,-0.51242620279092177,-0.49642116499797695,
  -0.48044930577417827,-0.46451052853110569,-0.44860473706182519,-0.43273183553983707,
  -0.41689172851818235,-0.40108432092840535,-0.38530951807962555,-0.36956722565757510,
  -0.35385734972364269,-0.33817979671398207,-0.32253447343850278,-0.30692128708002231,
  -0.29134014519332557,-0.27579095570426099,-0.26027362690883771,-0.24478806747233961,
  -0.22933418642845638,-0.21391189317840681,-0.19852109749004329,-0.18316170949705282,
  -0.16783363969803178,-0.15253679895572167,-0.13727109849612032,-0.12203644990765458,
  -0.10683276514039401,-0.09165995650522350,-0.07651793667302426,-0.06140661867388314,
  -0.04632591589630042,-0.03127574208643105,-0.01625601134725155,-0.00126663813786368,
   0.01369246272733727, 0.02862137607936485, 0.04352018639542355, 0.05838897779964274,
   0.07322783406378933, 0.08803683860802489, 0.10281607450161243, 0.11756562446362991,
   0.13228557086368359, 0.14697599572259623, 0.16163698071311866, 0.17626860716060286,
   0.19087095604369114, 0.20544410799498100, 0.21998814330169739, 0.23450314190636670,
   0.24898918340744544, 0.26344634705999492, 0.27787471177630507, 0.29227435612652902,
   0.30664535833932932, 0.32098779630249663, 0.33530174756354841, 0.34958728933035343,
   0.36384449847174732, 0.37807345151810029, 0.39227422466195133, 0.40644689375855048,
   0.42059153432646212, 0.43470822154815053, 0.44879703027052165, 0.46285803500551231,
   0.47689130993061696, 0.49089692888945680, 0.50487496539232124, 0.51882549261672373,
   0.53274858340789077, 0.54664431027933980, 0.56051274541336549, 0.57435396066157429,
   0.58816802754537501, 0.60195501725651335, 0.61571500065752960, 0.62944804828231005,
   0.64315423033651786, 0.65683361669809526, 0.67048627691774565, 0.68411228021941950,
   0.69771169550073209, 0.71128459133346489, 0.72483103596402065, 0.73835109731384918,
   0.75184484297988852, 0.76531234023504524, 0.77875365602857105, 0.79216885698654138,
   0.80555800941223210, 0.81892117928657526, 0.83225843226853358, 0.84556983369554095,
   0.85885544858389173, 0.87211534162911175, 0.88534957720638641, 0.89855821937093483,
   0.91174133185835249, 0.92489897808505039, 0.93803122114856985, 0.95113812382797236,
   0.96421974858418946, 0.97727615756039032, 0.99030741258230404, 1.00331357515859643,
   1.01629470648115627, 1.02925086742551031, 1.04218211855105358, 1.05508852010144882,
   1.06797013200490798, 1.08082701387450109, 1.09365922500849821, 1.10646682439061550,
   1.11924987069037374, 1.13200842226333043, 1.14474253715141616, 1.15745227308317888,
   1.17013768747406988, 1.18279883742674818, 1.19543577973129134, 1.20804857086549733,
   1.22063726699510311, 1.23320192397407968, 1.24574259734485149, 1.25825934233851910,
   1.27075221387512172, 1.28322126656387203, 1.29566655470334569, 1.30808813228172771,
   1.32048605297702237, 1.33286037015724101, 1.34521113688064475, 1.35753840589589991,
   1.36984222964230740, 1.38212266024994523, 1.39437974953990218, 1.40661354902441205,
   1.41882410990704222, 1.43101148308287729, 1.44317571913863119, 1.45531686835286656,
   1.46743498069607003, 1.47953010583085898, 1.49160229311208559, 1.50365159158697548,
   1.51567804999528710, 1.52768171676937681, 1.53966264003433850, 1.55162086760814133,
   1.56355644700169893, 1.57546942541899071, 1.58735984975712996, 1.59922776660648647,
   1.61107322225074157, 1.62289626266695852, 1.63469693352569156, 1.64647528019100919,
   1.65823134772056680, 1.66996518086566237, 1.68167682407129537, 1.69336632147614852,
   1.70503371691272743, 1.71667905390727182, 1.72830237567985900, 1.73990372514439051,
   1.75148314490858770, 1.76304067727403790, 1.77457636423613230, 1.78609024748411405,
   1.79758236840100993, 1.80905276806364368, 1.82050148724260308, 1.83192856640218205,
   1.84333404570035464, 1.85471796498873132, 1.86608036381247122, 1.87742128141027709,
   1.88874075671425090, 1.90003882834986637, 1.91131553463589676, 1.92257091358425614,
   1.93380500289998558, 1.94501783998108069, 1.95620946191840384, 1.96737990549557451,
   1.97852920718881653, 1.98965740316684658, 2.00076452929070303, 2.01185062111363022,
   2.02291571388088531, 2.03395984252958906, 2.04498304168855682, 2.05598534567809521,
   2.06696678850982840, 2.07792740388648767, 2.08886722520171730, 2.09978628553984903,
   2.11068461767567817, 2.12156225407422605, 2.13241922689051133, 2.14325556796929684,
   2.15407130884479914, 2.16486648074048649, 2.17564111456872133, 2.18639524093055160,
   2.19712889011533585, 2.20784209210051952, 2.21853487655125070, 2.22920727282010001,
   2.23985930994668925, 2.25049101665740148, 2.26110242136495865, 2.27169355216812185,
   2.28226443685127389, 2.29281510288403689, 2.30334557742090817, 2.31385588730083436,
   2.32434605904677793, 2.33481611886530915, 2.34526609264617791, 2.35569600596183948,
   2.36610588406700595, 2.37649575189817908, 2.38686563407314845, 2.39721555489051452,
   2.40754553832918106, 2.41785560804780753, 2.42814578738430331, 2.43841609935529169,
   2.44866656665552052,
]

FPWS_T_START = 50.0
FPWS_T_STEP  = 0.5

def _fpws_interp(T_F):
    """Catmull-Rom in log-space — exact port of fPwsInterp from merkel-engine.js"""
    n = len(LN_FPWS_TABLE)
    if T_F <= FPWS_T_START:
        return math.exp(LN_FPWS_TABLE[0])
    T_max = FPWS_T_START + (n - 1) * FPWS_T_STEP
    if T_F >= T_max:
        return math.exp(LN_FPWS_TABLE[n - 1])

    pos = (T_F - FPWS_T_START) / FPWS_T_STEP
    i   = int(pos)
    t   = pos - i

    p0 = LN_FPWS_TABLE[max(0, i - 1)]
    p1 = LN_FPWS_TABLE[i]
    p2 = LN_FPWS_TABLE[min(n - 1, i + 1)]
    p3 = LN_FPWS_TABLE[min(n - 1, i + 2)]

    a = -0.5*p0 + 1.5*p1 - 1.5*p2 + 0.5*p3
    b =      p0 - 2.5*p1 + 2.0*p2 - 0.5*p3
    c = -0.5*p0           + 0.5*p2
    d = p1

    return math.exp(((a*t + b)*t + c)*t + d)


def _h_sat(P_psi, T_F):
    """hSatImperial — exact port from merkel-engine.js"""
    fPws   = _fpws_interp(T_F)
    P_denom = P_psi - fPws
    if P_denom <= 0:
        return 999.0
    Ws = 0.62198 * fPws / P_denom
    return CP_DRY_AIR_BTU * T_F + Ws * (H_FG_BTU + CP_STEAM_BTU * T_F)


def _alt_to_psi_h1(alt_m):
    """H1: current JS — converts to feet first (physically correct)"""
    if alt_m == 0.0:
        return P_SEA_LEVEL_PSI
    alt_ft = alt_m / 0.3048
    x      = alt_ft / 10000.0
    numer  = ((0.547462*x - 7.67923)*x + 29.9309) * 0.491154
    denom  = 0.10803*x + 1.0
    return numer / denom


def _alt_to_psi_h2(alt_m):
    """H2: no feet conversion — meters passed directly to polynomial"""
    if alt_m == 0.0:
        return P_SEA_LEVEL_PSI
    x     = alt_m / 10000.0
    numer = ((0.547462*x - 7.67923)*x + 29.9309) * 0.491154
    denom = 0.10803*x + 1.0
    return numer / denom


def _merkel_kavl(hwt, cwt, wbt, lg, alt_m, use_h1=True):
    """
    Full Merkel KaV/L — Python port of merkelKaVL() from merkel-engine.js.
    use_h1=True → H1 (m→ft conversion); use_h1=False → H2 (meters direct)
    Returns (kavl_str, P_psi) matching JS parseFloat(kavl.toFixed(5)).toString()
    """
    if hwt <= cwt or cwt <= wbt or lg <= 0:
        return None, None

    WBT_F     = wbt * 1.8 + 32
    Range_F   = (hwt - cwt) * 1.8
    Approach_F = (cwt - wbt) * 1.8
    CWT_F     = WBT_F + Approach_F
    HWT_F     = CWT_F + Range_F

    if HWT_F >= 212.0:
        return "999.00000", None

    P_psi    = _alt_to_psi_h1(alt_m) if use_h1 else _alt_to_psi_h2(alt_m)
    h_air_in = _h_sat(P_psi, WBT_F)
    h_air_out = Range_F * lg + h_air_in

    total = 0.0
    for cheb in CHEBYSHEV_POINTS:
        T_i       = Range_F * cheb + CWT_F
        h_sat_i   = _h_sat(P_psi, T_i)
        h_air_i   = (h_air_out - h_air_in) * cheb + h_air_in
        driving   = h_sat_i - h_air_i
        if driving <= 0:
            return "999.00000", P_psi
        total += 0.25 / driving

    kavl = total * Range_F
    # Match JS: parseFloat(kavl.toFixed(5)).toString() — strips trailing zeros
    kavl_str = str(float(f"{kavl:.5f}"))
    return kavl_str, P_psi


# ============================================================
# PRESSURE COMPARISON TABLE (sanity check)
# ============================================================

def print_pressure_check():
    print("\n  PRESSURE SANITY CHECK (standard atm vs H1 vs H2):")
    print(f"  {'Alt(m)':>7s} {'Std(PSI)':>10s} {'H1(PSI)':>10s} {'H2(PSI)':>10s}  H1-match  H2-match")
    print(f"  {'─'*65}")
    alts = [0, 500, 1000, 1500, 2000]
    for alt_m in alts:
        alt_ft = alt_m / 0.3048
        # ICAO standard atmosphere formula (same as psychro engine)
        P_std_kpa = 101.325 * (1 - 6.8753e-6 * alt_ft)**5.2561
        P_std_psi = P_std_kpa / 6.89476
        P_h1 = _alt_to_psi_h1(alt_m)
        P_h2 = _alt_to_psi_h2(alt_m)
        h1_err = abs(P_h1 - P_std_psi)
        h2_err = abs(P_h2 - P_std_psi)
        print(f"  {alt_m:>7.0f}  {P_std_psi:>10.4f}  {P_h1:>10.4f}  {P_h2:>10.4f}  "
              f"Δ={h1_err:.4f}  Δ={h2_err:.4f}")
    print()


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 90)
    print("  MERKEL ALTITUDE VERIFICATION — JS Engine vs CTI GUI")
    print("  " + "─"*60)
    print("  Tests H1 (current: m→ft) and H2 (direct meters) against CTI GUI truth")
    print("=" * 90)

    print_pressure_check()

    # --- Test matrix: holistic coverage ---
    # Format: (hwt, cwt, wbt, lg, alt_m, label)
    TEST_CASES = [
        # --- Altitude sweep (fixed temps) ---
        (40.0, 28.0, 20.0, 1.0,    0.0, "ALT-0"),
        (40.0, 28.0, 20.0, 1.0,  500.0, "ALT-500"),
        (40.0, 28.0, 20.0, 1.0, 1000.0, "ALT-1000"),
        (40.0, 28.0, 20.0, 1.0, 1500.0, "ALT-1500"),
        (40.0, 28.0, 20.0, 1.0, 2000.0, "ALT-2000"),

        # --- High temps at altitude ---
        (55.0, 38.0, 25.0, 1.3,    0.0, "HI-ALT0"),
        (55.0, 38.0, 25.0, 1.3,  500.0, "HI-ALT500"),
        (55.0, 38.0, 25.0, 1.3, 1000.0, "HI-ALT1000"),
        (55.0, 38.0, 25.0, 1.3, 1500.0, "HI-ALT1500"),
        (55.0, 38.0, 25.0, 1.3, 2000.0, "HI-ALT2000"),

        # --- Low temps at altitude ---
        (35.0, 25.0, 18.0, 1.0,    0.0, "LO-ALT0"),
        (35.0, 25.0, 18.0, 1.0,  500.0, "LO-ALT500"),
        (35.0, 25.0, 18.0, 1.0, 1000.0, "LO-ALT1000"),
        (35.0, 25.0, 18.0, 1.0, 2000.0, "LO-ALT2000"),

        # --- High range ---
        (65.0, 45.0, 30.0, 1.5,    0.0, "RANGE-ALT0"),
        (65.0, 45.0, 30.0, 1.5,  500.0, "RANGE-ALT500"),
        (65.0, 45.0, 30.0, 1.5, 1000.0, "RANGE-ALT1000"),
        (65.0, 45.0, 30.0, 1.5, 2000.0, "RANGE-ALT2000"),

        # --- Various LG at altitude ---
        (50.0, 35.0, 25.0, 0.5, 1000.0, "LG0.5-1000m"),
        (50.0, 35.0, 25.0, 1.0, 1000.0, "LG1.0-1000m"),
        (50.0, 35.0, 25.0, 1.5, 1000.0, "LG1.5-1000m"),
        (50.0, 35.0, 25.0, 2.0, 1000.0, "LG2.0-1000m"),
        (50.0, 35.0, 25.0, 3.0, 1000.0, "LG3.0-1000m"),

        # --- Combo: all params vary ---
        (45.0, 32.0, 22.0, 1.2,  800.0, "COMBO-1"),
        (60.0, 42.0, 32.0, 1.8, 1200.0, "COMBO-2"),
        (38.0, 28.0, 18.0, 0.8,  600.0, "COMBO-3"),
        (70.0, 48.0, 35.0, 2.0, 1800.0, "COMBO-4"),
    ]

    print(f"  Launching CTI Toolkit (Merkel mode)...")
    bot = MerkelSiphon()
    if not bot.launch(visible=True):
        print("  [!] Failed to launch CTI Toolkit. Aborting.")
        return

    print(f"  CTI Toolkit ready. Running {len(TEST_CASES)} test cases...\n")
    print(f"  {'Label':<14s} {'HWT':>5s} {'CWT':>5s} {'WBT':>5s} {'LG':>4s} {'Alt':>5s}"
          f" {'GUI':>10s} {'H1':>10s} {'H2':>10s} {'H1-ok':>6s} {'H2-ok':>6s}")
    print(f"  {'─'*85}")

    h1_total = 0; h1_exact = 0
    h2_total = 0; h2_exact = 0
    mismatches = []

    for label, hwt, cwt, wbt, lg, alt in [(tc[5],tc[0],tc[1],tc[2],tc[3],tc[4]) for tc in TEST_CASES]:
        gui_str = bot.process_point(hwt, cwt, wbt, lg, alt)
        h1_str, _ = _merkel_kavl(hwt, cwt, wbt, lg, alt, use_h1=True)
        h2_str, _ = _merkel_kavl(hwt, cwt, wbt, lg, alt, use_h1=False)

        if gui_str in ("N/A", None, ""):
            print(f"  {label:<14s} {hwt:5.1f} {cwt:5.1f} {wbt:5.1f} {lg:4.1f} {alt:5.0f}"
                  f"  {'N/A':>10s} {h1_str or '':>10s} {h2_str or '':>10s}")
            continue

        # GUI gives 5 decimal string (CTI display format)
        gui_val = float(gui_str)

        h1_val  = float(h1_str) if h1_str else None
        h2_val  = float(h2_str) if h2_str else None

        h1_match = (h1_str == gui_str) if (h1_str and gui_str) else False
        h2_match = (h2_str == gui_str) if (h2_str and gui_str) else False

        h1_total += 1; h1_exact += int(h1_match)
        h2_total += 1; h2_exact += int(h2_match)

        sym_h1 = "✓" if h1_match else "✗"
        sym_h2 = "✓" if h2_match else "✗"

        print(f"  {label:<14s} {hwt:5.1f} {cwt:5.1f} {wbt:5.1f} {lg:4.1f} {alt:5.0f}"
              f" {gui_str:>10s} {h1_str or '':>10s} {h2_str or '':>10s}"
              f"  {sym_h1:>5s}  {sym_h2:>5s}")

        if not h1_match or not h2_match:
            h1_delta = abs(h1_val - gui_val) if h1_val else 999
            h2_delta = abs(h2_val - gui_val) if h2_val else 999
            mismatches.append((label, hwt, cwt, wbt, lg, alt, gui_str, h1_str, h2_str, h1_delta, h2_delta))

    bot.kill()

    print(f"\n  {'─'*85}")
    print(f"\n  SUMMARY:")
    print(f"    H1 (m→ft conversion): {h1_exact}/{h1_total} exact  ({100*h1_exact/max(1,h1_total):.1f}%)")
    print(f"    H2 (meters direct):   {h2_exact}/{h2_total} exact  ({100*h2_exact/max(1,h2_total):.1f}%)")

    if mismatches:
        print(f"\n  MISMATCHES (showing worst cases):")
        # Sort by h1_delta (show biggest errors first)
        mismatches.sort(key=lambda x: -x[9])
        print(f"  {'Label':<14s} {'Alt':>5s} {'GUI':>10s} {'H1':>10s} {'H2':>10s} {'H1-Δ':>10s} {'H2-Δ':>10s}")
        for label, hwt, cwt, wbt, lg, alt, gui, h1, h2, d1, d2 in mismatches[:10]:
            print(f"  {label:<14s} {alt:5.0f} {gui:>10s} {h1 or '':>10s} {h2 or '':>10s} {d1:>10.6f} {d2:>10.6f}")

    winner = None
    if h1_exact > h2_exact:
        winner = "H1 (m→ft conversion) — current JS engine is CORRECT"
    elif h2_exact > h1_exact:
        winner = "H2 (meters direct) — JS engine needs fixing (remove feet conversion)"
    elif h1_exact == h1_total:
        winner = "BOTH correct (no altitude effect visible at display precision)"
    else:
        winner = "NEITHER — deeper investigation needed"

    print(f"\n  {'='*85}")
    print(f"  VERDICT: {winner}")
    print(f"  {'='*85}\n")


if __name__ == "__main__":
    main()
