import html
import random
import streamlit as st
#python3 -m streamlit run app.py


st.set_page_config(page_title="Cat Profile Generator", layout="centered")

# =====================================================================
#  LOOK & FEEL (custom CSS: fonts, colors, cards)
# =====================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.stApp { background: #f3f5f9; }
html, body, .stApp, .stApp button, .stApp input {
    font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
}
footer { visibility: hidden; }

/* ---- Header ---- */
.hero {
    text-align: center;
    padding: 1rem 0 1.2rem;
    border-bottom: 1px solid #dfe3ea;
    margin-bottom: 0.5rem;
}
.hero-title {
    font-size: 2.1rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #111827;
}
.hero-sub { color: #6b7280; font-size: 1rem; margin-top: 0.3rem; }

/* ---- Tabs, labels, inputs ---- */
.stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 1.5rem; }
.stTabs [data-baseweb="tab"] p {
    color: #1f2937;
    font-weight: 600;
    font-size: 1rem;
}
.stTextInput label p { color: #1f2937 !important; font-weight: 600; }
.stTextInput [data-baseweb="input"],
.stTextInput [data-baseweb="base-input"],
.stTextInput input {
    background: #ffffff !important;
    color: #111827 !important;
    border-radius: 8px;
}
.stTextInput [data-baseweb="input"] { border: 1px solid #cbd2dc; }

/* ---- Buttons ---- */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    padding: 0.55rem 1.5rem;
    border: 1px solid #1e3a8a;
    background: #ffffff;
    color: #1e3a8a;
}
.stButton > button p { color: inherit !important; }
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    background: #1e3a8a;
    color: #ffffff;
    border-color: #1e3a8a;
}

/* ---- Cards ---- */
.card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 1px 3px rgba(17, 24, 39, 0.06);
    margin: 1rem 0;
    color: #1f2937;
}
.center { text-align: center; }
.monogram {
    width: 84px;
    height: 84px;
    border-radius: 50%;
    background: #1e3a8a;
    color: #ffffff;
    font-size: 2.2rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 0.8rem;
}
.monogram.small { width: 52px; height: 52px; font-size: 1.4rem; margin-bottom: 0.5rem; }
.cat-name {
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: #111827;
}
.sub { color: #6b7280; }
.tag {
    display: inline-block;
    margin-top: 0.7rem;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    padding: 0.2rem 0.8rem;
    border-radius: 999px;
    font-size: 0.9rem;
    font-weight: 500;
    color: #334155;
}
.card-title {
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6b7280;
    margin-bottom: 0.6rem;
}
.chip {
    display: inline-block;
    background: #eef2ff;
    color: #1e3a8a;
    padding: 0.3rem 0.9rem;
    border-radius: 999px;
    margin: 0.2rem;
    font-weight: 600;
    font-size: 0.92rem;
}
.row {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.65rem 0;
    border-bottom: 1px solid #eef0f4;
}
.row:last-child { border-bottom: none; }
.k { font-weight: 600; color: #4b5563; }
.v { text-align: right; color: #111827; }

/* ---- Stat bars ---- */
.stat { margin: 1rem 0; }
.stat-label {
    display: flex;
    justify-content: space-between;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 0.35rem;
}
.bar { background: #e5e7eb; border-radius: 999px; height: 8px; overflow: hidden; }
.fill { height: 100%; border-radius: 999px; background: #1e3a8a; }

/* ---- Fun fact + compatibility ---- */
.fact {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #1e3a8a;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    color: #334155;
    margin: 1rem 0;
}
.score-label {
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6b7280;
}
.score {
    font-size: 4rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: #1e3a8a;
    line-height: 1.15;
}
.verdict { font-size: 1.3rem; font-weight: 600; color: #111827; }
.pair-names { color: #6b7280; margin-top: 0.8rem; font-size: 0.95rem; }
.mini-name { font-size: 1.2rem; font-weight: 700; color: #111827; }
</style>
"""

# =====================================================================
#  DATA: lists of possible attributes (add your own to make it funnier!)
# =====================================================================
BREEDS = [
    "Maine Coon", "Siamese", "Persian", "Bengal", "Ragdoll", "Sphynx",
    "British Shorthair", "Scottish Fold", "Tabby", "Calico", "Tuxedo",
    "Orange Tabby", "Russian Blue", "Mystery Alley Cat",
]
FUR_COLORS = [
    "Midnight black", "Snowy white", "Ginger orange", "Smoky gray",
    "Cream", "Chocolate brown", "Silver", "Tortoiseshell",
]
EYE_COLORS = ["Emerald green", "Golden amber", "Ice blue", "Copper", "Mismatched (one blue, one green)"]
PERSONALITIES = [
    "Dramatic", "Chill", "Sneaky", "Cuddly", "Royal", "Chaotic", "Curious",
    "Grumpy", "Playful", "Mysterious", "Lazy", "Adventurous",
]
FAVORITE_FOODS = [
    "Tuna", "Salmon pate", "Chicken treats", "Cheese (stolen)", "Cardboard",
    "Anything on your plate", "Crunchy kibble", "Shrimp",
]
NAP_SPOTS = [
    "Your keyboard", "A sunny windowsill", "Inside a cardboard box",
    "The freshly folded laundry", "On top of the fridge", "Your pillow",
    "The warm spot you just left",
]
SECRET_TALENTS = [
    "Can open doors", "Knocks things off tables with perfect aim",
    "Appears the second a can opens", "Can fit through any gap",
    "Predicts when you're about to sit down", "Sleeps 20 hours straight",
    "Hears a treat bag from three rooms away",
]
SUPERPOWERS = [
    "Invisibility (when it's bath time)", "Teleporting to the one spot you just cleaned",
    "Staring into your soul", "3 AM zoomies", "Landing on all four paws, always",
    "Turning any lap into a bed",
]
CAT_SIGNS = [
    "The Midnight Zoomie", "The Sunbeam Sleeper", "The Box Collector",
    "The Laser Chaser", "The Curtain Climber", "The Lap Conqueror",
    "The Window Watcher",
]
MOODS = [
    "Pleased with itself", "Plotting something", "Dozing", "Startled by nothing",
    "Feeling affectionate", "Up to no good", "Purring softly",
]
CAT_FACTS = [
    "Cats sleep roughly 12 to 16 hours a day.",
    "A group of cats is called a clowder.",
    "A cat's nose print is unique, just like a human fingerprint.",
    "Cats can rotate their ears about 180 degrees.",
    "Cats can't taste sweetness.",
    "Most cats have 18 toes: five on each front paw and four on each back paw.",
]

# Compatibility results: (minimum score, title, description)
VERDICTS = [
    (85, "Excellent match", "Highly compatible. Likely to share space, food, and naps without conflict."),
    (70, "Strong match", "Generally compatible, with plenty of common ground."),
    (50, "Moderate match", "A workable pairing. Expect some friction over food and territory."),
    (30, "Challenging match", "Significant differences. Separate food bowls and space are recommended."),
    (0, "Poor match", "Very low compatibility. Careful, gradual introductions are advised."),
]


# =====================================================================
#  LOGIC
# =====================================================================
def pretty(name):
    """Title-case a name and make it safe to show inside HTML."""
    return html.escape(name.strip().title())


def initial(name):
    """First letter of the name, used for the circular badge."""
    letter = next((ch for ch in name.strip() if ch.isalpha()), "?")
    return html.escape(letter.upper())


def generate_cat(name, seed_number):
    """Build a random cat profile. The same name + seed always gives the same cat."""
    rng = random.Random(f"{name.lower().strip()}-{seed_number}")
    return {
        "mood": rng.choice(MOODS),
        "breed": rng.choice(BREEDS),
        "age": rng.randint(1, 18),
        "fur": rng.choice(FUR_COLORS),
        "eyes": rng.choice(EYE_COLORS),
        "personality": rng.sample(PERSONALITIES, 3),
        "food": rng.choice(FAVORITE_FOODS),
        "nap_spot": rng.choice(NAP_SPOTS),
        "talent": rng.choice(SECRET_TALENTS),
        "superpower": rng.choice(SUPERPOWERS),
        "sign": rng.choice(CAT_SIGNS),
        "lucky_number": rng.randint(1, 99),
        "fact": rng.choice(CAT_FACTS),
        "lives": rng.randint(1, 9),
        "chaos": rng.randint(1, 100),
        "cuteness": rng.randint(60, 100),
        "sleep_hours": rng.randint(12, 20),
    }


def compatibility(name_a, name_b):
    """Compare two cats. Order of names doesn't matter (A+B = B+A)."""
    a = generate_cat(name_a, 0)
    b = generate_cat(name_b, 0)
    pair_rng = random.Random("-".join(sorted([name_a.lower().strip(), name_b.lower().strip()])))

    scores = {
        "Energy match": 100 - abs(a["chaos"] - b["chaos"]),
        "Nap synergy": 100 - abs(a["sleep_hours"] - b["sleep_hours"]) * 8,
        "Snack sharing": 100 if a["food"] == b["food"] else pair_rng.randint(35, 85),
        "Chemistry": pair_rng.randint(30, 100),
    }
    shared = [t for t in a["personality"] if t in b["personality"]]

    average = sum(scores.values()) / len(scores)
    total = min(100, round(average + 8 * len(shared)))   # +8 for each shared trait

    for minimum, title, blurb in VERDICTS:
        if total >= minimum:
            verdict, description = title, blurb
            break

    first, second = name_a.strip().title(), name_b.strip().title()
    ship_name = first[: max(1, len(first) // 2)] + second[len(second) // 2:]

    return {
        "a": a, "b": b, "scores": scores, "shared": shared,
        "total": total, "verdict": verdict, "description": description,
        "ship": ship_name,
    }


# =====================================================================
#  HTML BUILDERS (each returns one HTML string, no blank lines inside)
# =====================================================================
def stat_bar(label, value, text):
    return (
        '<div class="stat"><div class="stat-label">'
        f"<span>{label}</span><span>{text}</span></div>"
        f'<div class="bar"><div class="fill" style="width:{value}%"></div></div></div>'
    )


def chips(items):
    return "".join(f'<span class="chip">{item}</span>' for item in items)


def header_card(name, cat):
    return (
        '<div class="card center">'
        f'<div class="monogram">{initial(name)}</div>'
        f'<div class="cat-name">{pretty(name)}</div>'
        f'<div class="sub">{cat["breed"]} &middot; {cat["age"]} years old</div>'
        f'<div class="tag">Mood: {cat["mood"]}</div>'
        "</div>"
    )


def personality_card(cat):
    return (
        '<div class="card center">'
        '<div class="card-title">Personality</div>'
        f'{chips(cat["personality"])}'
        "</div>"
    )


def stats_card(cat):
    return (
        '<div class="card">'
        '<div class="card-title">Stats</div>'
        + stat_bar("Lives remaining", round(cat["lives"] / 9 * 100), f'{cat["lives"]} / 9')
        + stat_bar("Chaos level", cat["chaos"], f'{cat["chaos"]}%')
        + stat_bar("Cuteness", cat["cuteness"], f'{cat["cuteness"]}%')
        + stat_bar("Sleep per day", round(cat["sleep_hours"] / 24 * 100), f'{cat["sleep_hours"]} hrs')
        + "</div>"
    )


def details_card(cat):
    details = [
        ("Fur", cat["fur"]),
        ("Eyes", cat["eyes"]),
        ("Favorite food", cat["food"]),
        ("Favorite nap spot", cat["nap_spot"]),
        ("Secret talent", cat["talent"]),
        ("Superpower", cat["superpower"]),
        ("Cat sign", cat["sign"]),
        ("Lucky number", str(cat["lucky_number"])),
    ]
    rows = "".join(
        f'<div class="row"><span class="k">{k}</span><span class="v">{v}</span></div>'
        for k, v in details
    )
    return f'<div class="card"><div class="card-title">Details</div>{rows}</div>'


def fact_card(cat):
    return f'<div class="fact"><b>Did you know?</b> {cat["fact"]}</div>'


def mini_card(name, cat):
    return (
        '<div class="card center">'
        f'<div class="monogram small">{initial(name)}</div>'
        f'<div class="mini-name">{pretty(name)}</div>'
        f'<div class="sub">{cat["breed"]}</div>'
        f'<div>{chips(cat["personality"])}</div>'
        "</div>"
    )


def score_card(result):
    return (
        '<div class="card center">'
        '<div class="score-label">Compatibility score</div>'
        f'<div class="score">{result["total"]}%</div>'
        f'<div class="verdict">{result["verdict"]}</div>'
        f'<div class="sub">{result["description"]}</div>'
        f'<div class="pair-names">Pair name: <b>{html.escape(result["ship"])}</b></div>'
        "</div>"
    )


def breakdown_card(result):
    bars = "".join(stat_bar(label, value, f"{value}%") for label, value in result["scores"].items())
    if result["shared"]:
        shared_html = (
            '<div class="card-title" style="margin-top:1.2rem">Shared traits (+8 points each)</div>'
            f'<div>{chips(result["shared"])}</div>'
        )
    else:
        shared_html = '<div class="sub" style="margin-top:1rem">No shared personality traits.</div>'
    return (
        '<div class="card">'
        '<div class="card-title">Compatibility breakdown</div>'
        f"{bars}{shared_html}"
        "</div>"
    )


# =====================================================================
#  PAGE LAYOUT
# =====================================================================
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="hero"><div class="hero-title">Cat Profile Generator</div>'
    '<div class="hero-sub">Generate a detailed profile for any cat, or compare two cats for compatibility.</div></div>',
    unsafe_allow_html=True,
)

# session_state remembers values between reruns (Streamlit reruns the script on every click)
if "generated" not in st.session_state:
    st.session_state.generated = False
if "seed_number" not in st.session_state:
    st.session_state.seed_number = 0
if "compare" not in st.session_state:
    st.session_state.compare = False

tab_profile, tab_match = st.tabs(["Cat Profile", "Compatibility"])

# ---------------------------- Tab 1: single cat ----------------------------
with tab_profile:
    name = st.text_input("Cat's name", placeholder="e.g. Whiskers", key="single_name")

    col1, col2 = st.columns(2)
    if col1.button("Generate", type="primary", use_container_width=True):
        st.session_state.generated = True
        st.session_state.seed_number = 0
    if col2.button("Re-roll", use_container_width=True):
        st.session_state.generated = True
        st.session_state.seed_number += 1

    if st.session_state.generated:
        if not name.strip():
            st.warning("Please enter a cat name first.")
        else:
            cat = generate_cat(name, st.session_state.seed_number)
            st.markdown(header_card(name, cat), unsafe_allow_html=True)
            st.markdown(personality_card(cat), unsafe_allow_html=True)
            st.markdown(stats_card(cat), unsafe_allow_html=True)
            st.markdown(details_card(cat), unsafe_allow_html=True)
            st.markdown(fact_card(cat), unsafe_allow_html=True)

# ---------------------------- Tab 2: compatibility ----------------------------
with tab_match:
    st.write("")
    left, right = st.columns(2)
    name_a = left.text_input("First cat", placeholder="e.g. Whiskers", key="cat_a")
    name_b = right.text_input("Second cat", placeholder="e.g. Luna", key="cat_b")

    if st.button("Check compatibility", type="primary", use_container_width=True):
        st.session_state.compare = True

    if st.session_state.compare:
        if not name_a.strip() or not name_b.strip():
            st.warning("Enter both cat names first.")
        elif name_a.strip().lower() == name_b.strip().lower():
            st.info("Those are the same cat. Try two different names.")
        else:
            result = compatibility(name_a, name_b)
            st.markdown(score_card(result), unsafe_allow_html=True)
            st.markdown(breakdown_card(result), unsafe_allow_html=True)

            pair_left, pair_right = st.columns(2)
            pair_left.markdown(mini_card(name_a, result["a"]), unsafe_allow_html=True)
            pair_right.markdown(mini_card(name_b, result["b"]), unsafe_allow_html=True)
