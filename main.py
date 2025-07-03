from fastapi import FastAPI
from pydantic import BaseModel
import swisseph as swe
import datetime
import pytz

app = FastAPI()

# Set path and Ayanamsa
swe.set_ephe_path("ephe")
swe.set_sid_mode(swe.SIDM_LAHIRI)

class BirthDetails(BaseModel):
    date: str
    time: str
    timezone: str
    latitude: float
    longitude: float

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.TRUE_NODE
}

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha", "Ardra", "Punarvasu",
    "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
    "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati"
]

NAKSHATRA_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"
]

VIMSHOTTARI_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17
}

def get_sign(degree: float):
    return ZODIAC_SIGNS[int(degree // 30)]

def get_nakshatra(moon_long):
    index = int(moon_long // (360 / 27))
    return NAKSHATRAS[index], NAKSHATRA_LORDS[index], index, (moon_long % (360 / 27)) / (360 / 27)

def calculate_dasha(start_lord, nakshatra_frac, birth_dt):
    sequence = [
        "Ketu", "Venus", "Sun", "Moon", "Mars", 
        "Rahu", "Jupiter", "Saturn", "Mercury"
    ]
    idx = sequence.index(start_lord)
    years_left = VIMSHOTTARI_YEARS[start_lord] * (1 - nakshatra_frac)
    end_dt = birth_dt + datetime.timedelta(days=years_left*365.25)
    return {
        "current": start_lord,
        "ends": end_dt.strftime("%Y-%m")
    }

def to_utc_julian(date_str, time_str, tz_str):
    local = pytz.timezone(tz_str)
    dt_local = local.localize(datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
    dt_utc = dt_local.astimezone(pytz.utc)
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60.0)
    return jd, dt_utc

def determine_house(degree, house_cusps):
    for i in range(12):
        start = house_cusps[i]
        end = house_cusps[(i + 1) % 12]
        if start < end:
            if start <= degree < end:
                return i + 1
        else:
            if degree >= start or degree < end:
                return i + 1
    return None

@app.post("/vedic-chart")
def generate_chart(birth: BirthDetails):
    jd_ut, dt_utc = to_utc_julian(birth.date, birth.time, birth.timezone)

    cusps, ascmc = swe.houses(jd_ut, birth.latitude, birth.longitude, b'P')
    asc_deg = round(ascmc[0], 4)
    house_cusps = [round(deg, 4) for deg in cusps[:12]]
    asc_sign = get_sign(asc_deg)

    planetary_positions = {}

    moon_long = None

    for name, code in PLANETS.items():
        pos, _ = swe.calc_ut(jd_ut, code, swe.FLG_SIDEREAL)
        deg = round(pos[0], 4)
        sign = get_sign(deg)
        house = determine_house(deg, house_cusps)
        planetary_positions[name] = {
            "degree": round(deg % 30, 2),
            "sign": sign,
            "house": house
        }
        if name == "Moon":
            moon_long = deg

    rahu_deg = planetary_positions["Rahu"]["degree"] + (ZODIAC_SIGNS.index(planetary_positions["Rahu"]["sign"]) * 30)
    ketu_deg = (rahu_deg + 180) % 360
    ketu_sign = get_sign(ketu_deg)
    ketu_house = determine_house(ketu_deg, house_cusps)
    planetary_positions["Ketu"] = {
        "degree": round(ketu_deg % 30, 2),
        "sign": ketu_sign,
        "house": ketu_house
    }

    # 🌙 Nakshatra + Dasha
    nakshatra_name, nakshatra_lord, nakshatra_index, nakshatra_frac = get_nakshatra(moon_long)
    dasha = calculate_dasha(nakshatra_lord, nakshatra_frac, dt_utc)

    return {
        "julian_day": jd_ut,
        "ascendant": {
            "degree": asc_deg,
            "sign": asc_sign
        },
        "planetary_positions": planetary_positions,
        "house_cusps": house_cusps,
        "moon_nakshatra": nakshatra_name,
        "current_dasha": dasha
    }
