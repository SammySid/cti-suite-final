"""
test_x87_hypothesis.py
======================
Tests whether the 59 remaining H parity failures are caused by x87 80-bit
extended precision vs IEEE 754 64-bit doubles.

Method:
  - Re-compute W and H using Python's decimal module at 50 digits (≈ "infinite precision")
  - Compare against H_bin (binary's displayed value) and H_js (our 64-bit result)
  - If decimal result rounds to H_bin: the binary is computing the "exact" value and our
    64-bit is overshooting/undershooting. The 80-bit x87 is closer to infinite precision.
  - If decimal result rounds to H_js: the binary is using a LESS accurate value than us
    (unusual — would mean x87 adds error vs exact arithmetic).

Tested on:
  - Alt=0 failures (+0.0001): H_js > H_bin
  - Alt=1000 failures (−0.0001): H_js < H_bin
"""
import csv, math, os
from decimal import Decimal, getcontext
getcontext().prec = 50   # 50-digit precision (~166-bit)

HERE = os.path.dirname(os.path.abspath(__file__))

# ── Constants (all as Decimal for maximum precision) ──────────────────────────
C9_WATER = Decimal('-5.516256')
C9_ICE   = Decimal('6.3925247') - Decimal(1000).ln()
C8_W  = Decimal('-5800.2206')
C10_W = Decimal('-0.048640239')
C11_W = Decimal('4.1764768e-5')
C12_W = Decimal('-1.4452093e-8')
C13_W = Decimal('6.5459673')
L0    = Decimal('2501.0')
CpS   = Decimal('1.805')
CpW   = Decimal('4.186')
L_COEFF = CpW - CpS
MW_MA   = Decimal('0.62198')

# ── F_ALT_TABLE (1°C step) stored as float64 but look up via Decimal interp ──
F_ALT_TABLE = [
    [1.00403158595907, 1.00401873749121, 1.00400718430652, 1.00399688708958, 1.00398781338272, 1.00397993722473, 1.00397323878959, 1.00396770402522,
     1.00396332429217, 1.00396009600239, 1.00395802025792, 1.00395710248965, 1.00395735209602, 1.00395878208178, 1.00396140869667, 1.00396525107422,
     1.00397033087039, 1.00397667190237, 1.00398429978728, 1.00399324158090, 1.00400352541640, 1.00401518014304, 1.00402823496496, 1.00404271907986,
     1.00405866131773, 1.00407608977959, 1.00409503147623, 1.00411551196692, 1.00413755499813, 1.00416118214227, 1.00418641243645, 1.00421326202113,
     1.00424174377894, 1.00427186697332, 1.00430363688733, 1.00433705446230, 1.00437211593663, 1.00440881248447, 1.00444712985447, 1.00448704800848,
     1.00452854076032, 1.00457157541449, 1.00461611240488, 1.00466210493352, 1.00470949860930, 1.00475823108670, 1.00480823170451, 1.00485942112459,
     1.00491171097055, 1.00496500346649, 1.00501919107578, 1.00507415613971, 1.00512977051628, 1.00518589521888, 1.00524238005507, 1.00529906326526,
     1.00535577116146, 1.00541231776601, 1.00546850445030, 1.00552411957351, 1.00557893812132, 1.00563272134466, 1.00568521639841, 1.00573615598016,
     1.00578525796890],
    [1.00382704963733, 1.00381588620097, 1.00380588199838, 1.00379701016169, 1.00378925016243, 1.00378258745023, 1.00377701309158, 1.00377252340854,
     1.00376911961747, 1.00376680746779, 1.00376559688064, 1.00376550158768, 1.00376653876978, 1.00376872869575, 1.00377209436107, 1.00377666112662,
     1.00378245635743, 1.00378950906136, 1.00379784952787, 1.00380750896673, 1.00381851914675, 1.00383091203452, 1.00384471943310, 1.00385997262080,
     1.00387670198988, 1.00389493668528, 1.00391470424333, 1.00393603023054, 1.00395893788225, 1.00398344774140, 1.00400957729726, 1.00403734062414,
     1.00406674802015, 1.00409780564587, 1.00413051516315, 1.00416487337377, 1.00420087185823, 1.00423849661443, 1.00427772769642, 1.00431853885311,
     1.00436089716705, 1.00440476269308, 1.00445008809712, 1.00449681829488, 1.00454489009056, 1.00459423181563, 1.00464476296751, 1.00469639384834,
     1.00474902520367, 1.00480254786121, 1.00485684236954, 1.00491177863688, 1.00496721556977, 1.00502300071180, 1.00507896988240, 1.00513494681547,
     1.00519074279821, 1.00524615630977, 1.00530097266001, 1.00535496362824, 1.00540788710191, 1.00545948671538, 1.00550949148862, 1.00555761546595,
     1.00560355735478],
    [1.00362995706826, 1.00362041132937, 1.00361191716807, 1.00360445847398, 1.00359802498229, 1.00359261191256, 1.00358821960738, 1.00358485317117,
     1.00358252210885, 1.00358123996459, 1.00358102396055, 1.00358189463558, 1.00358387548398, 1.00358699259420, 1.00359127428759, 1.00359675075709,
     1.00360345370603, 1.00361141598679, 1.00362067123954, 1.00363125353100, 1.00364319699315, 1.00365653546193, 1.00367130211603, 1.00368752911555,
     1.00370524724078, 1.00372448553091, 1.00374527092275, 1.00376762788945, 1.00379157807927, 1.00381713995426, 1.00384432842902, 1.00387315450941,
     1.00390362493130, 1.00393574179925, 1.00396950222531, 1.00400489796768, 1.00404191506948, 1.00408053349746, 1.00412072678074, 1.00416246164952,
     1.00420569767384, 1.00425038690226, 1.00429647350063, 1.00434389339081, 1.00439257388938, 1.00444243334637, 1.00449338078403, 1.00454531553549,
     1.00459812688355, 1.00465169369937, 1.00470588408120, 1.00476055499315, 1.00481555190384, 1.00487070842522, 1.00492584595121, 1.00498077329651,
     1.00503528633525, 1.00508916763979, 1.00514218611939, 1.00519409665897, 1.00524463975784, 1.00529354116840, 1.00534051153490, 1.00538524603215,
     1.00542742400426],
    [1.00344058150765, 1.00343259534982, 1.00342557580705, 1.00341951601333, 1.00341441447814, 1.00341027472517, 1.00340710493106, 1.00340491756412,
     1.00340372902308, 1.00340355927577, 1.00340443149791, 1.00340637171177, 1.00340940842496, 1.00341357226912, 1.00341889563867, 1.00342541232952,
     1.00343315717780, 1.00344216569861, 1.00345247372472, 1.00346411704532, 1.00347713104472, 1.00349155034111, 1.00350740842528, 1.00352473729932,
     1.00354356711540, 1.00356392581445, 1.00358583876491, 1.00360932840144, 1.00363441386370, 1.00366111063499, 1.00368943018108, 1.00371937958885,
     1.00375096120507, 1.00378417227511, 1.00381900458168, 1.00385544408352, 1.00389347055419, 1.00393305722075, 1.00397417040251, 1.00401676914974,
     1.00406080488241, 1.00410622102893, 1.00415295266486, 1.00420092615164, 1.00425005877532, 1.00430025838529, 1.00435142303301, 1.00440344061073,
     1.00445618849025, 1.00450953316158, 1.00456332987173, 1.00461742226342, 1.00467164201382, 1.00472580847322, 1.00477972830385, 1.00483319511853,
     1.00488598911944, 1.00493787673684, 1.00498861026777, 1.00503792751483, 1.00508555142487, 1.00513118972773, 1.00517453457496, 1.00521526217857,
     1.00525303244971],
]
F_ALT_T_MIN = -5; F_ALT_T_STEP = 1; F_ALT_T_N = 65; F_ALT_A_STEP = 500

def feP_dec(T_float, P_float):
    """f lookup via Decimal arithmetic."""
    T = Decimal(str(T_float)); P = Decimal(str(P_float))
    D101325 = Decimal('101.325')
    # P→alt
    ratio = P / D101325
    exponent = Decimal('1') / Decimal('5.2559')
    import decimal
    alt_m = (Decimal('1') - ratio**exponent) / Decimal('2.25577e-5')
    # T index
    t_float = (T - Decimal(str(F_ALT_T_MIN))) / Decimal(str(F_ALT_T_STEP))
    t_lo = max(0, min(F_ALT_T_N - 2, int(t_float)))
    frac_t = max(Decimal('0'), min(Decimal('1'), t_float - t_lo))
    # alt index
    a_float = alt_m / Decimal(str(F_ALT_A_STEP))
    a_lo = max(0, min(len(F_ALT_TABLE) - 2, int(a_float)))
    frac_a = max(Decimal('0'), min(Decimal('1'), a_float - a_lo))
    # bilinear interp
    rLo = F_ALT_TABLE[a_lo]; rHi = F_ALT_TABLE[a_lo + 1]
    fLo = Decimal(str(rLo[t_lo])) + frac_t*(Decimal(str(rLo[t_lo+1])) - Decimal(str(rLo[t_lo])))
    fHi = Decimal(str(rHi[t_lo])) + frac_t*(Decimal(str(rHi[t_lo+1])) - Decimal(str(rHi[t_lo])))
    return fLo + frac_a * (fHi - fLo)

def pws_dec(T_float):
    """Hyland-Wexler via Decimal at 50-digit precision."""
    import decimal
    T = Decimal(str(T_float))
    K = T + Decimal('273.15')
    if T >= 0:
        ln_val = (C8_W/K + C9_WATER + C10_W*K + C11_W*K*K + C12_W*K**3 +
                  C13_W * K.ln())
    else:
        C9_ice = Decimal('6.3925247') - (Decimal('1000').ln())
        ln_val = (Decimal('-5674.5359')/K + C9_ice
                  - Decimal('0.0096778430')*K + Decimal('6.2215701e-7')*K*K
                  + Decimal('2.0747825e-9')*K**3 - Decimal('9.484024e-13')*K**4
                  + Decimal('4.1635019')*K.ln())
    return ln_val.exp()

def W_calc_dec(dbt, wbt, alt):
    """Compute W (humidity ratio) at 50-digit Decimal precision."""
    P = Decimal('101.325') * (Decimal('1') - Decimal('2.25577e-5') * Decimal(str(alt)))**Decimal('5.2559')
    Pws_wbt = pws_dec(wbt)
    f_wbt   = feP_dec(wbt, float(P))
    fPw     = f_wbt * Pws_wbt
    Ws      = MW_MA * fPw / (P - fPw)
    dbt_d   = Decimal(str(dbt)); wbt_d = Decimal(str(wbt))
    denom   = L0 + CpS*dbt_d - CpW*wbt_d
    num     = (L0 - L_COEFF*wbt_d)*Ws - (dbt_d - wbt_d)
    W       = max(Decimal('0'), num / denom)
    H       = Decimal('1.006') * dbt_d + W * (L0 + CpS * dbt_d)
    return W, H

def W_calc_f64(dbt, wbt, alt):
    """Same calculation in IEEE 754 float64 (what our JS does)."""
    C9_w = -5.516256; C9_i = 6.3925247 - math.log(1000)
    C8 = -5800.2206; C10 = -0.048640239; C11 = 4.1764768e-5
    C12 = -1.4452093e-8; C13 = 6.5459673
    def pws64(T):
        K = T + 273.15
        if T >= 0:
            ln = C8/K + C9_w + C10*K + C11*K*K + C12*K**3 + C13*math.log(K)
        else:
            ln = (-5674.5359/K + C9_i - 0.0096778430*K + 6.2215701e-7*K*K
                  + 2.0747825e-9*K**3 - 9.484024e-13*K**4 + 4.1635019*math.log(K))
        return math.exp(ln)
    def feP64(T, P):
        alt_m = (1.0 - (P/101.325)**(1.0/5.2559)) / 2.25577e-5
        t_float = (T - (-5)) / 1; t_lo = max(0, min(63, int(math.floor(t_float))))
        frac_t = max(0.0, min(1.0, t_float - t_lo))
        a_float = alt_m / 500; a_lo = max(0, min(2, int(math.floor(a_float))))
        frac_a = max(0.0, min(1.0, a_float - a_lo))
        rLo = F_ALT_TABLE[a_lo]; rHi = F_ALT_TABLE[a_lo+1]
        fLo = rLo[t_lo] + frac_t*(rLo[t_lo+1] - rLo[t_lo])
        fHi = rHi[t_lo] + frac_t*(rHi[t_lo+1] - rHi[t_lo])
        return fLo + frac_a*(fHi - fLo)
    P = 101.325*(1 - 2.25577e-5*alt)**5.2559
    Pws_wbt = pws64(wbt); f_wbt = feP64(wbt, P)
    fPw = f_wbt*Pws_wbt; Ws = 0.62198*fPw/(P - fPw)
    denom = 2501.0 + 1.805*dbt - 4.186*wbt
    W = max(0.0, ((2501.0 - 2.381*wbt)*Ws - (dbt - wbt)) / denom)
    H = 1.006*dbt + W*(2501.0 + 1.805*dbt)
    return W, H

# ── Load failing cases ────────────────────────────────────────────────────────
rows = list(csv.DictReader(open(os.path.join(HERE, 'dp_parity_probe.csv'))))

# Find +0.0001 failures (alt=0) and -0.0001 failures (alt≥500)
pos_fails = []   # H_js > H_bin
neg_fails = []   # H_js < H_bin
for r in rows:
    dbt, wbt, alt = float(r['dbt']), float(r['wbt']), float(r['alt'])
    h_b = float(r['h_bin'])
    _, H64 = W_calc_f64(dbt, wbt, alt)
    H64r = round(H64, 4)
    if H64r != h_b:
        diff = H64r - h_b
        if diff > 0: pos_fails.append((dbt, wbt, alt, H64r, h_b))
        else:        neg_fails.append((dbt, wbt, alt, H64r, h_b))

print(f"Total +0.0001 failures (JS too high): {len(pos_fails)}")
print(f"Total -0.0001 failures (JS too low):  {len(neg_fails)}")
print()

# Test the hypothesis on representative cases from each group
print("="*70)
print("HYPOTHESIS TEST: Does 50-digit Decimal H agree with H_bin or H_js?")
print("="*70)
print(f"  A decimal result = H_bin → binary is 'exact', our 64-bit is imprecise")
print(f"  A decimal result = H_js  → binary uses LESS precision than 64-bit (unlikely)")
print()

def test_case(label, dbt, wbt, alt, H64r, h_bin):
    W_d, H_d = W_calc_dec(dbt, wbt, alt)
    H_dec_exact = float(H_d)
    H_dec_4dp   = round(H_dec_exact, 4)
    W64, H64 = W_calc_f64(dbt, wbt, alt)
    verdict = "→ H_bin" if H_dec_4dp == h_bin else ("→ H_js" if H_dec_4dp == H64r else "→ OTHER")
    print(f"  [{label}] dbt={dbt} wbt={wbt} alt={alt:.0f}")
    print(f"    H_bin (binary)  = {h_bin:.6f}")
    print(f"    H_js  (float64) = {H64r:.6f}  (diff = {H64r-h_bin:+.4f})")
    print(f"    H_dec (50-dig)  = {H_dec_exact:.10f}  → 4dp = {H_dec_4dp:.4f}  {verdict}")
    print(f"    W_64  = {W64:.10f}")
    print(f"    W_dec = {float(W_d):.10f}")
    print(f"    ΔW    = {W64 - float(W_d):+.2e}")
    print()

print("── +0.0001 cases (H_js > H_bin, alt=0) ──────────────────────────────")
for case in pos_fails[:4]:
    test_case("+0.0001", *case)

print("── −0.0001 cases (H_js < H_bin, alt≥500) ────────────────────────────")
for case in neg_fails[:4]:
    test_case("-0.0001", *case)

# Summary
print("="*70)
print("CONCLUSION")
pos_to_bin  = sum(1 for (dbt,wbt,alt,H64r,hb) in pos_fails if round(float(W_calc_dec(dbt,wbt,alt)[1]),4)==hb)
pos_to_js   = len(pos_fails) - pos_to_bin
neg_to_bin  = sum(1 for (dbt,wbt,alt,H64r,hb) in neg_fails if round(float(W_calc_dec(dbt,wbt,alt)[1]),4)==hb)
neg_to_js   = len(neg_fails) - neg_to_bin
print(f"  +0.0001 cases: {pos_to_bin}/{len(pos_fails)} decimal→H_bin  {pos_to_js}/{len(pos_fails)} decimal→H_js")
print(f"  -0.0001 cases: {neg_to_bin}/{len(neg_fails)} decimal→H_bin  {neg_to_js}/{len(neg_fails)} decimal→H_js")
print()
if pos_to_bin + neg_to_bin == len(pos_fails) + len(neg_fails):
    print("  ✅ ALL failures: decimal agrees with H_bin. 64-bit float imprecision CONFIRMED.")
    print("  The binary's x87 80-bit is closer to exact arithmetic; JS 64-bit overshoots/undershoots.")
elif pos_to_js + neg_to_js == len(pos_fails) + len(neg_fails):
    print("  ❌ ALL failures: decimal agrees with H_js. Binary uses LESS precision (unexpected).")
else:
    print("  ⚠ Mixed results — multiple error sources present.")
