import numpy as np
from scipy.interpolate import Akima1DInterpolator

def AskaniyExtrapolator(x, y, curve):
    interp = Akima1DInterpolator(x, y)
    x1 = 550
    y1 = interp(x1)
    line1 = lambda wl: y[0] + (wl - x[0]) * (y1 - y[0]) / (x1 - x[0])
    line2 = lambda wl: y1 + (wl - x1) * (y[-1] - y1) / (x[-1] - x1)
    br = []
    for nm in curve:
        if nm < x[0]:
            br.append(line1(nm))
        elif nm > x[-1]:
            br.append(line2(nm))
        else:
            br.append(interp(nm))
    return br

def from_indeces(data):
    result = {}
    for index, value in data["indices"].items():
        bands = index.split("-")
        if result == {}:
            result.update({bands[0]: 1.0})
        if bands[0] in result:
            k = filters[data["filters"]][bands[0]]["zp"] - filters[data["filters"]][bands[1]]["zp"]
            result.update({bands[1]: result[bands[0]] * 10**(0.4*(value + k))})
    nm = []
    br = []
    for band, value in result.items():
        nm.append(filters[data["filters"]][band]["nm"])
        br.append(value / (filters[data["filters"]][band]["nm"]/1e9)**2)
    data.update({"nm": nm, "br": br})
    return data

def subtract_sun(spectrum, sun):
    nm = []
    br = []
    interp = Akima1DInterpolator(spectrum["nm"], spectrum["br"])
    for i in range(len(sun["br"])):
        corrected = interp(sun["nm"][i]) / sun["br"][i]
        if not np.isnan(corrected):
            br.append(corrected)
            nm.append(sun["nm"][i])
    spectrum.update({"nm": nm, "br": br})
    return spectrum

def to_rgb(spectrum, mode="1", albedo=None, inp_bit=None, exp_bit=None, rnd=0, gamma=False, srgb=False, html=False):
    spectrum = np.clip(spectrum, 0, None)
    if inp_bit:
        spectrum = (spectrum + 1) / 2**inp_bit
    if srgb:
        xyz = np.sum(spectrum[:, np.newaxis] * xyz_curves, axis=0)
        rgb = xyz_to_sRGB(xyz)
    else:
        rgb = np.sum(spectrum[:, np.newaxis] * rgb_curves, axis=0)
    try:
        if mode in ["1", "chromaticity"]:
            rgb /= np.max(rgb)
        elif mode in ["2", "normalization"]:
            rgb /= 2*rgb[1]
        elif mode in ["3", "albedo"]:
            if albedo is None:
                pass
            else:
                rgb = albedo * rgb / rgb[1]
    except ZeroDivisionError:
        rgb = np.array([0.5, 0.5, 0.5])
    if gamma:
        g = np.vectorize(lambda x: 12.92*x if x < 0.0031308 else 1.055 * x**(1.0/2.4) - 0.055)
        rgb = g(rgb)
    if html:
        return "#{:02x}{:02x}{:02x}".format(*[int(round(b)) for b in to_bit(8, rgb)])
    if exp_bit:
        rgb = to_bit(exp_bit, rgb)
    if rnd != 0:
        return tuple([round(color, rnd) for color in rgb])
    else:
        return tuple([int(color) for color in rgb])

def xyz_from_xy(x, y):
    return np.array((x, y, 1-x-y))

def to_bit(bit, rgb):
    return rgb * 2**bit - 1

def xyz_to_sRGB(xyz):
    # https://scipython.com/blog/converting-a-spectrum-to-a-colour/
    r = xyz_from_xy(0.64, 0.33)
    g = xyz_from_xy(0.30, 0.60)
    b = xyz_from_xy(0.15, 0.06)
    white = xyz_from_xy(0.3127, 0.3291) # D65
    M = np.vstack((r, g, b)).T
    MI = np.linalg.inv(M)
    wscale = MI.dot(white)
    T = MI / wscale[:, np.newaxis]
    rgb = T.dot(xyz)
    if np.any(rgb < 0): # We're not in the sRGB gamut: approximate by desaturating
        w = - np.min(rgb)
        rgb += w
    return rgb


# Pivot wavelengths and ZeroPoints of filter bandpasses
# https://www.stsci.edu/~INS/2010CalWorkshop/pickles.pdf

filters = {
    "Tycho": {
        "B": {"nm": 419.6, "zp": -0.108},
        "V": {"nm": 530.5, "zp": -0.030}
    },
    "Landolt": {
        "U": {"nm": 354.6, "zp": 0.761},
        "B": {"nm": 432.6, "zp": -0.103},
        "V": {"nm": 544.5, "zp": -0.014},
        "R": {"nm": 652.9, "zp": 0.154},
        "I": {"nm": 810.4, "zp": 0.405}
    },
    "UBVRI": {
        "U": {"nm": 358.9, "zp": 0.763},
        "B": {"nm": 437.2, "zp": -0.116},
        "V": {"nm": 549.3, "zp": -0.014},
        "R": {"nm": 652.7, "zp": 0.165},
        "I": {"nm": 789.1, "zp": 0.368}
    },
    "Stromgren": {
        "us": {"nm": 346.1, "zp": -0.290},
        "vs": {"nm": 410.7, "zp": -0.316},
        "bs": {"nm": 467.0, "zp": -0.181},
        "ys": {"nm": 547.6, "zp": -0.041}
    },
    "Sloan Air": {
        "u'": {"nm": 355.2, "zp": -0.033},
        "g'": {"nm": 476.6, "zp": -0.009},
        "r'": {"nm": 622.6, "zp": 0.004},
        "i'": {"nm": 759.8, "zp": 0.008},
        "z'": {"nm": 890.6, "zp": 0.009}
    },
    "Sloan Vacuum": {
        "u": {"nm": 355.7, "zp": -0.034},
        "g": {"nm": 470.3, "zp": -0.002},
        "r": {"nm": 617.6, "zp": 0.003},
        "i": {"nm": 749.0, "zp": 0.011},
        "z": {"nm": 889.2, "zp": 0.007}
    }
}

# CIE RGB colour matching function: Stiles & Burch 1959 10 Degree RGB CMFs
# https://colour.readthedocs.io/en/v0.3.15/generated/colour.RGB_CMFS.html?highlight=dataset.cmfs

cmf_rgb = np.array([
    [390.0, 0.0015, -0.0004, 0.0062],
    [395.0, 0.0038, -0.001, 0.0161],
    [400.0, 0.0089, -0.0025, 0.04],
    [405.0, 0.0188, -0.0059, 0.0906],
    [410.0, 0.035, -0.0119, 0.1802],
    [415.0, 0.0531, -0.0201, 0.3088],
    [420.0, 0.0702, -0.0289, 0.467],
    [425.0, 0.0763, -0.0338, 0.6152],
    [430.0, 0.0745, -0.0349, 0.7638],
    [435.0, 0.0561, -0.0276, 0.8778],
    [440.0, 0.0323, -0.0169, 0.9755],
    [445.0, -0.0044, 0.0024, 1.0019],
    [450.0, -0.0478, 0.0283, 0.9996],
    [455.0, -0.097, 0.0636, 0.9139],
    [460.0, -0.1586, 0.1082, 0.8297],
    [465.0, -0.2235, 0.1617, 0.7417],
    [470.0, -0.2848, 0.2201, 0.6134],
    [475.0, -0.3346, 0.2796, 0.472],
    [480.0, -0.3776, 0.3428, 0.3495],
    [485.0, -0.4136, 0.4086, 0.2564],
    [490.0, -0.4317, 0.4716, 0.1819],
    [495.0, -0.4452, 0.5491, 0.1307],
    [500.0, -0.435, 0.626, 0.091],
    [505.0, -0.414, 0.7097, 0.058],
    [510.0, -0.3673, 0.7935, 0.0357],
    [515.0, -0.2845, 0.8715, 0.02],
    [520.0, -0.1855, 0.9477, 0.0095],
    [525.0, -0.0435, 0.9945, 0.0007],
    [530.0, 0.127, 1.0203, -0.0043],
    [535.0, 0.3129, 1.0375, -0.0064],
    [540.0, 0.5362, 1.0517, -0.0082],
    [545.0, 0.7722, 1.039, -0.0094],
    [550.0, 1.0059, 1.0029, -0.0097],
    [555.0, 1.271, 0.9698, -0.0097],
    [560.0, 1.5574, 0.9162, -0.0093],
    [565.0, 1.8465, 0.8571, -0.0087],
    [570.0, 2.1511, 0.7823, -0.008],
    [575.0, 2.425, 0.6953, -0.0073],
    [580.0, 2.6574, 0.5966, -0.0063],
    [585.0, 2.9151, 0.5063, -0.00537],
    [590.0, 3.0779, 0.4203, -0.00445],
    [595.0, 3.1613, 0.336, -0.00357],
    [600.0, 3.1673, 0.2591, -0.00277],
    [605.0, 3.1048, 0.1917, -0.00208],
    [610.0, 2.9462, 0.1367, -0.0015],
    [615.0, 2.7194, 0.0938, -0.00103],
    [620.0, 2.4526, 0.0611, -0.00068],
    [625.0, 2.17, 0.0371, -0.000442],
    [630.0, 1.8358, 0.0215, -0.000272],
    [635.0, 1.5179, 0.0112, -0.000141],
    [640.0, 1.2428, 0.0044, -5.49e-05],
    [645.0, 1.007, 7.8e-05, -2.2e-06],
    [650.0, 0.7827, -0.001368, 2.37e-05],
    [655.0, 0.5934, -0.001988, 2.86e-05],
    [660.0, 0.4442, -0.002168, 2.61e-05],
    [665.0, 0.3283, -0.002006, 2.25e-05],
    [670.0, 0.2394, -0.001642, 1.82e-05],
    [675.0, 0.1722, -0.001272, 1.39e-05],
    [680.0, 0.1221, -0.000947, 1.03e-05],
    [685.0, 0.0853, -0.000683, 7.38e-06],
    [690.0, 0.0586, -0.000478, 5.22e-06],
    [695.0, 0.0408, -0.000337, 3.67e-06],
    [700.0, 0.0284, -0.000235, 2.56e-06],
    [705.0, 0.0197, -0.000163, 1.76e-06],
    [710.0, 0.0135, -0.000111, 1.2e-06],
    [715.0, 0.00924, -7.48e-05, 8.17e-07],
    [720.0, 0.00638, -5.08e-05, 5.55e-07],
    [725.0, 0.00441, -3.44e-05, 3.75e-07],
    [730.0, 0.00307, -2.34e-05, 2.54e-07],
    [735.0, 0.00214, -1.59e-05, 1.71e-07],
    [740.0, 0.00149, -1.07e-05, 1.16e-07],
    [745.0, 0.00105, -7.23e-06, 7.85e-08],
    [750.0, 0.000739, -4.87e-06, 5.31e-08],
    [755.0, 0.000523, -3.29e-06, 3.6e-08],
    [760.0, 0.000372, -2.22e-06, 2.44e-08],
    [765.0, 0.000265, -1.5e-06, 1.65e-08],
    [770.0, 0.00019, -1.02e-06, 1.12e-08],
    [775.0, 0.000136, -6.88e-07, 7.53e-09],
    [780.0, 9.84e-05, -4.65e-07, 5.07e-09],
    [785.0, 7.13e-05, -3.12e-07, 3.4e-09],
    [790.0, 5.18e-05, -2.08e-07, 2.27e-09],
    [795.0, 3.77e-05, -1.37e-07, 1.5e-09],
    [800.0, 2.76e-05, -8.8e-08, 9.86e-10],
    [805.0, 2.03e-05, -5.53e-08, 6.39e-10],
    [810.0, 1.49e-05, -3.36e-08, 4.07e-10],
    [815.0, 1.1e-05, -1.96e-08, 2.53e-10],
    [820.0, 8.18e-06, -1.09e-08, 1.52e-10],
    [825.0, 6.09e-06, -5.7e-09, 8.64e-11],
    [830.0, 4.55e-06, -2.77e-09, 4.42e-11]
])
rgb_nm = list(cmf_rgb[:, 0])
rgb_curves = cmf_rgb[:, 1:]
rgb_curves /= np.sum(rgb_curves, axis=0)

cmf_xyz = np.array([
	[360.0, 0.000000122200, 0.000000013398, 0.000000535027],
	[365.0, 0.000000919270, 0.000000100650, 0.000004028300],
	[370.0, 0.000005958600, 0.000000651100, 0.000026143700],
	[375.0, 0.000033266000, 0.000003625000, 0.000146220000],
	[380.0, 0.000159952000, 0.000017364000, 0.000704776000],
	[385.0, 0.000662440000, 0.000071560000, 0.002927800000],
	[390.0, 0.002361600000, 0.000253400000, 0.010482200000],
	[395.0, 0.007242300000, 0.000768500000, 0.032344000000],
	[400.0, 0.019109700000, 0.002004400000, 0.086010900000],
	[405.0, 0.043400000000, 0.004509000000, 0.197120000000],
	[410.0, 0.084736000000, 0.008756000000, 0.389366000000],
	[415.0, 0.140638000000, 0.014456000000, 0.656760000000],
	[420.0, 0.204492000000, 0.021391000000, 0.972542000000],
	[425.0, 0.264737000000, 0.029497000000, 1.282500000000],
	[430.0, 0.314679000000, 0.038676000000, 1.553480000000],
	[435.0, 0.357719000000, 0.049602000000, 1.798500000000],
	[440.0, 0.383734000000, 0.062077000000, 1.967280000000],
	[445.0, 0.386726000000, 0.074704000000, 2.027300000000],
	[450.0, 0.370702000000, 0.089456000000, 1.994800000000],
	[455.0, 0.342957000000, 0.106256000000, 1.900700000000],
	[460.0, 0.302273000000, 0.128201000000, 1.745370000000],
	[465.0, 0.254085000000, 0.152761000000, 1.554900000000],
	[470.0, 0.195618000000, 0.185190000000, 1.317560000000],
	[475.0, 0.132349000000, 0.219940000000, 1.030200000000],
	[480.0, 0.080507000000, 0.253589000000, 0.772125000000],
	[485.0, 0.041072000000, 0.297665000000, 0.570600000000],
	[490.0, 0.016172000000, 0.339133000000, 0.415254000000],
	[495.0, 0.005132000000, 0.395379000000, 0.302356000000],
	[500.0, 0.003816000000, 0.460777000000, 0.218502000000],
	[505.0, 0.015444000000, 0.531360000000, 0.159249000000],
	[510.0, 0.037465000000, 0.606741000000, 0.112044000000],
	[515.0, 0.071358000000, 0.685660000000, 0.082248000000],
	[520.0, 0.117749000000, 0.761757000000, 0.060709000000],
	[525.0, 0.172953000000, 0.823330000000, 0.043050000000],
	[530.0, 0.236491000000, 0.875211000000, 0.030451000000],
	[535.0, 0.304213000000, 0.923810000000, 0.020584000000],
	[540.0, 0.376772000000, 0.961988000000, 0.013676000000],
	[545.0, 0.451584000000, 0.982200000000, 0.007918000000],
	[550.0, 0.529826000000, 0.991761000000, 0.003988000000],
	[555.0, 0.616053000000, 0.999110000000, 0.001091000000],
	[560.0, 0.705224000000, 0.997340000000, 0.000000000000],
	[565.0, 0.793832000000, 0.982380000000, 0.000000000000],
	[570.0, 0.878655000000, 0.955552000000, 0.000000000000],
	[575.0, 0.951162000000, 0.915175000000, 0.000000000000],
	[580.0, 1.014160000000, 0.868934000000, 0.000000000000],
	[585.0, 1.074300000000, 0.825623000000, 0.000000000000],
	[590.0, 1.118520000000, 0.777405000000, 0.000000000000],
	[595.0, 1.134300000000, 0.720353000000, 0.000000000000],
	[600.0, 1.123990000000, 0.658341000000, 0.000000000000],
	[605.0, 1.089100000000, 0.593878000000, 0.000000000000],
	[610.0, 1.030480000000, 0.527963000000, 0.000000000000],
	[615.0, 0.950740000000, 0.461834000000, 0.000000000000],
	[620.0, 0.856297000000, 0.398057000000, 0.000000000000],
	[625.0, 0.754930000000, 0.339554000000, 0.000000000000],
	[630.0, 0.647467000000, 0.283493000000, 0.000000000000],
	[635.0, 0.535110000000, 0.228254000000, 0.000000000000],
	[640.0, 0.431567000000, 0.179828000000, 0.000000000000],
	[645.0, 0.343690000000, 0.140211000000, 0.000000000000],
	[650.0, 0.268329000000, 0.107633000000, 0.000000000000],
	[655.0, 0.204300000000, 0.081187000000, 0.000000000000],
	[660.0, 0.152568000000, 0.060281000000, 0.000000000000],
	[665.0, 0.112210000000, 0.044096000000, 0.000000000000],
	[670.0, 0.081260600000, 0.031800400000, 0.000000000000],
	[675.0, 0.057930000000, 0.022601700000, 0.000000000000],
	[680.0, 0.040850800000, 0.015905100000, 0.000000000000],
	[685.0, 0.028623000000, 0.011130300000, 0.000000000000],
	[690.0, 0.019941300000, 0.007748800000, 0.000000000000],
	[695.0, 0.013842000000, 0.005375100000, 0.000000000000],
	[700.0, 0.009576880000, 0.003717740000, 0.000000000000],
	[705.0, 0.006605200000, 0.002564560000, 0.000000000000],
	[710.0, 0.004552630000, 0.001768470000, 0.000000000000],
	[715.0, 0.003144700000, 0.001222390000, 0.000000000000],
	[720.0, 0.002174960000, 0.000846190000, 0.000000000000],
	[725.0, 0.001505700000, 0.000586440000, 0.000000000000],
	[730.0, 0.001044760000, 0.000407410000, 0.000000000000],
	[735.0, 0.000727450000, 0.000284041000, 0.000000000000],
	[740.0, 0.000508258000, 0.000198730000, 0.000000000000],
	[745.0, 0.000356380000, 0.000139550000, 0.000000000000],
	[750.0, 0.000250969000, 0.000098428000, 0.000000000000],
	[755.0, 0.000177730000, 0.000069819000, 0.000000000000],
	[760.0, 0.000126390000, 0.000049737000, 0.000000000000],
	[765.0, 0.000090151000, 0.000035540500, 0.000000000000],
	[770.0, 0.000064525800, 0.000025486000, 0.000000000000],
	[775.0, 0.000046339000, 0.000018338400, 0.000000000000],
	[780.0, 0.000033411700, 0.000013249000, 0.000000000000],
	[785.0, 0.000024209000, 0.000009619600, 0.000000000000],
	[790.0, 0.000017611500, 0.000007012800, 0.000000000000],
	[795.0, 0.000012855000, 0.000005129800, 0.000000000000],
	[800.0, 0.000009413630, 0.000003764730, 0.000000000000],
	[805.0, 0.000006913000, 0.000002770810, 0.000000000000],
	[810.0, 0.000005093470, 0.000002046130, 0.000000000000],
	[815.0, 0.000003767100, 0.000001516770, 0.000000000000],
	[820.0, 0.000002795310, 0.000001128090, 0.000000000000],
	[825.0, 0.000002082000, 0.000000842160, 0.000000000000],
	[830.0, 0.000001553140, 0.000000629700, 0.000000000000]
])
xyz_nm = list(cmf_xyz[:, 0])
xyz_curves = cmf_xyz[:, 1:]
#xyz_curves /= np.sum(xyz_curves, axis=0)