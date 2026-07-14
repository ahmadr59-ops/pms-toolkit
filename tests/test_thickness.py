from pmskit.thickness import required_thickness, governing_case, y_coefficient, bar_to_mpa

def test_bar_to_mpa():
    assert abs(bar_to_mpa(20) - 2.0) < 1e-9

def test_pressure_design_thickness_hand_check():
    # A106B NPS8 D=219.1mm, P=20 bar, S=120 MPa, E=W=1, Y=0.4 -> t ~ 1.814 mm
    r = required_thickness(20, 219.1, 120, Y=0.4)
    assert abs(r["t_pressure_design_mm"] - 1.814) < 0.01

def test_allowances_and_mill_tolerance():
    r = required_thickness(20, 219.1, 120, Y=0.4, c_mm=3.0, mill_tol=0.125)
    # (1.814 + 3.0)/0.875 = 5.50
    assert abs(r["T_nominal_to_order_mm"] - 5.50) < 0.02

def test_y_coefficient():
    assert y_coefficient("ferritic", 400) == 0.4
    assert y_coefficient("ferritic", 540) == 0.7
    assert y_coefficient("austenitic", 600) == 0.7

def test_governing_case_picks_worst():
    pts = [(38, 19.6), (400, 10.2)]
    s = lambda T: {38: 120, 400: 80}.get(T, 100)
    g = governing_case(pts, 219.1, s, c_mm=3.0)
    assert g["temp_C"] in (38, 400)
    # low-temp high-pressure governs here
    assert g["press_barg"] == 19.6
