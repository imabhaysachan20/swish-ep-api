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
    date: str  # e.g. "2002-11-02"
    time: str  # e.g. "21:09"
    timezone: str  # e.g. "Asia/Kolkata"
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

def get_sign(degree: float):
    return ZODIAC_SIGNS[int(degree // 30)]

def to_utc_julian(date_str, time_str, tz_str):
    local = pytz.timezone(tz_str)
    dt_local = local.localize(datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
    dt_utc = dt_local.astimezone(pytz.utc)
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60.0)
    return jd

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
    jd_ut = to_utc_julian(birth.date, birth.time, birth.timezone)

    cusps, ascmc = swe.houses(jd_ut, birth.latitude, birth.longitude, b'P')
    asc_deg = round(ascmc[0], 4)
    house_cusps = [round(deg, 4) for deg in cusps[:12]]
    asc_sign = get_sign(asc_deg)

    planetary_positions = {}

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

    # Add Ketu
    rahu_deg = planetary_positions["Rahu"]["degree"] + (ZODIAC_SIGNS.index(planetary_positions["Rahu"]["sign"]) * 30)
    ketu_deg = (rahu_deg + 180) % 360
    ketu_sign = get_sign(ketu_deg)
    ketu_house = determine_house(ketu_deg, house_cusps)
    planetary_positions["Ketu"] = {
        "degree": round(ketu_deg % 30, 2),
        "sign": ketu_sign,
        "house": ketu_house
    }

    return {
        "julian_day": jd_ut,
        "ascendant": {
            "degree": asc_deg,
            "sign": asc_sign
        },
        "planetary_positions": planetary_positions,
        "house_cusps": house_cusps
    }
