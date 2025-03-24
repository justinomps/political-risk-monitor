import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys and Secrets
GUARDIAN_API_KEY = os.getenv('GUARDIAN_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
MONGODB_URI = os.getenv('MONGODB_URI')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
THENEWSAPI_KEY = os.getenv('THENEWSAPI_KEY')

# Database settings
DATABASE_NAME = 'newsmonitor'

# Collections
COLLECTION_ARTICLES = 'articles'
COLLECTION_EVENTS = 'events'
COLLECTION_SUMMARIES = 'summaries'
COLLECTION_USERS = 'users'

# News collection settings
NEWS_SOURCES = [
    'theguardian.com',
    'nytimes.com',
    'washingtonpost.com',
    'apnews.com',
    'reuters.com',
    'npr.org',
    'bbc.com',
    'cnn.com',
    'foxnews.com',
    'politico.com'
]

# Framework categories
CATEGORIES = {
    "electoral_integrity": {
        "name": "Breakdown of Electoral Integrity",
        "description": "Concerns about voting systems, election processes, and representation",
        "keywords": [
            "voter suppression", "election fraud", "ballot access", 
            "voter purge", "gerrymandering", "election interference",
            "voting rights", "election commission", "vote count",
            "election monitors", "ballot", "electoral college"
        ],
        "yellow_indicators": [
            "voter id law", "gerrymandering", "voter roll purge",
            "limited early voting", "polling station closures"
        ],
        "orange_indicators": [
            "major voter purge", "election interference", "ballot access restricted", 
            "overturning local election", "mass disqualification",
            "removing election officials", "changing voting rules"
        ],
        "red_indicators": [
            "cancel election", "postpone election", "delay national election", 
            "overturn national election", "suspend voting rights",
            "invalidate results", "military control of election"
        ]
    },
    "political_purges": {
        "name": "Political Purges & Criminalization of Opposition",
        "description": "Targeting of political opponents or minority groups through legal or extra-legal means",
        "keywords": [
            "opposition leader", "political prisoner", "dissent crackdown",
            "government critic", "political prosecution", "political firing",
            "activist arrest", "deportation", "civil service", "loyalty",
            "political asylum", "immunity revoked"
        ],
        "yellow_indicators": [
            "government critic", "investigate opposition", "fire official", 
            "political prosecution", "threatening opposition", "intimidation"
        ],
        "orange_indicators": [
            "opposition leader arrested", "political prisoner", "mass firing", 
            "loyalty test", "activist deportation", "gag order",
            "exile", "political ban", "parliamentary immunity"
        ],
        "red_indicators": [
            "mass imprisonment", "opposition banned", "disappearance", 
            "exile opposition", "opposition leadership", "torture",
            "extrajudicial detention", "political party banned"
        ]
    },
    "political_violence": {
        "name": "Government-Sanctioned Political Violence",
        "description": "Use of force and intimidation against political opposition or civilians",
        "keywords": [
            "paramilitary", "militia", "political violence", "protest crackdown",
            "armed group", "violent suppression", "police brutality", 
            "political killing", "death squad", "vigilante", "intimidation"
        ],
        "yellow_indicators": [
            "violence rhetoric", "support militia", "intimidation campaign", 
            "threaten violence", "inflammatory speech", "excessive force"
        ],
        "orange_indicators": [
            "paramilitary group", "armed supporters", "violent suppression", 
            "police brutality", "political assault", "protesters injured",
            "raid headquarters", "violent intimidation", "armed police"
        ],
        "red_indicators": [
            "mass killing", "death squad", "government sanctioned violence", 
            "political assassination", "extrajudicial killing", "shoot to kill",
            "massacre", "disappearance", "torture", "mass casualties"
        ]
    },
    "civil_liberties": {
        "name": "Curtailment of Civil Liberties",
        "description": "Restrictions on freedom of speech, assembly, movement, and other civil rights",
        "keywords": [
            "emergency powers", "suspend rights", "protest ban", "assembly restriction",
            "free speech", "civil liberties", "surveillance", "privacy violation",
            "habeas corpus", "due process", "detention", "warrantless search"
        ],
        "yellow_indicators": [
            "restrict protest", "surveillance increase", "media pressure", 
            "legal threat", "speech restriction", "monitoring dissent"
        ],
        "orange_indicators": [
            "emergency powers", "suspend specific right", "ban assembly", 
            "indefinite detention", "censorship", "internet restrictions",
            "shutdown communication", "mass surveillance", "no-protest zones"
        ],
        "red_indicators": [
            "suspend constitution", "martial law", "suspend habeas corpus", 
            "mass detention", "curfew", "shoot on sight",
            "internet shutdown", "communication blackout", "house arrest"
        ]
    },
    "military_suppression": {
        "name": "Military Used for Internal Suppression",
        "description": "Deployment of military forces against civilian population or for domestic law enforcement",
        "keywords": [
            "military deployment", "national guard", "martial law", "domestic military",
            "military police", "troops deployed", "armed forces", "internal security",
            "military crackdown", "deploy soldiers", "domestic operation"
        ],
        "yellow_indicators": [
            "national guard activated", "military police", "troops standby", 
            "security operation", "military presence", "show of force"
        ],
        "orange_indicators": [
            "military deployment", "troops deployed", "active duty domestic", 
            "military checkpoint", "soldiers patrol", "armed personnel carriers",
            "military curfew", "military detention", "armed presence"
        ],
        "red_indicators": [
            "martial law", "military crackdown", "military rule", "shoot to kill order",
            "tanks in streets", "military takeover", "coup", "junta",
            "military government", "suspend civilian authority"
        ]
    },
    "media_censorship": {
        "name": "Mass Media Censorship",
        "description": "Control, suppression, or manipulation of news media and information flow",
        "keywords": [
            "media shutdown", "press freedom", "journalist arrest", "censorship", 
            "internet shutdown", "social media ban", "media control", "news blackout", 
            "disinformation", "propaganda", "state media", "fake news law"
        ],
        "yellow_indicators": [
            "media pressure", "journalist harassment", "fact checking", 
            "licensing requirement", "limit access", "selective briefings",
            "threaten media", "discredit reporting", "propaganda increase"
        ],
        "orange_indicators": [
            "journalist arrest", "media shutdown", "website block", 
            "social media restriction", "revoke press credentials",
            "raid newsroom", "fine publication", "seize equipment", "gag order"
        ],
        "red_indicators": [
            "internet shutdown", "mass media control", "criminal journalism", 
            "foreign media banned", "state takeover", "imprisonment for reporting",
            "confiscate media", "exile journalists", "nationwide censorship"
        ]
    },
    "asset_seizure": {
        "name": "Seizure of Assets & Political Retaliation",
        "description": "Economic attacks on political opponents through asset seizure, directed taxation, or other financial means",
        "keywords": [
            "asset freeze", "property seizure", "bank account", "confiscation", 
            "nationalization", "wealth tax", "expropriation", "financial sanction", 
            "politically motivated audit", "eminent domain", "targeted tax"
        ],
        "yellow_indicators": [
            "targeted audit", "financial investigation", "asset disclosure", 
            "selective enforcement", "political donor", "tax scrutiny",
            "business pressure", "regulatory targeting", "funding block"
        ],
        "orange_indicators": [
            "asset freeze", "bank account seized", "business shutdown", 
            "selective taxation", "charitable foundation", "political funds",
            "contract cancellation", "license revocation", "punitive fine"
        ],
        "red_indicators": [
            "mass confiscation", "nationalization", "property seizure", 
            "wealth redistribution", "business expropriation", "currency control",
            "funds confiscation", "economic purge", "asset stripping"
        ]
    },
    "judicial_independence": {
        "name": "Erosion of Judicial Independence",
        "description": "Weakening of judicial oversight and independent courts",
        "keywords": [
            "court packing", "judge removal", "judicial reform", "constitutional court",
            "supreme court", "judicial independence", "rule of law", "court ruling",
            "judiciary", "chief justice", "judicial review"
        ],
        "yellow_indicators": [
            "criticism of judges", "court reform proposal", "judicial appointments",
            "court expansion", "judicial restraint"
        ],
        "orange_indicators": [
            "court packing", "removal of judges", "ignore court ruling",
            "judicial appointments procedure", "oversight reduction"
        ],
        "red_indicators": [
            "dissolution of court", "mass replacement of judges", "judicial functions suspended",
            "parallel court system", "criminal charges against judges"
        ]
    },
    "information_manipulation": {
        "name": "Information Manipulation & Disinformation",
        "description": "Coordinated disinformation campaigns and manipulation of information ecosystem",
        "keywords": [
            "disinformation", "fake news", "propaganda", "fact check", "algorithm",
            "social media", "troll farm", "bot network", "foreign influence",
            "information warfare", "deep fake"
        ],
        "yellow_indicators": [
            "official misinformation", "label fact checks", "government propaganda",
            "media pressure", "algorithm control", "government talking points"
        ],
        "orange_indicators": [
            "troll farm", "disinformation campaign", "algorithm manipulation",
            "foreign influence operation", "coordinated inauthentic behavior",
            "ban fact-checking", "official fabrication"
        ],
        "red_indicators": [
            "centralized information control", "mass deception", "criminalize truth",
            "reality denial", "memory hole", "information blackout",
            "criminalize counter-narrative"
        ]
    },
    "institutional_erosion": {
        "name": "Erosion of Key Democratic Institutions",
        "description": "Weakening of oversight bodies, electoral systems, and bureaucratic independence",
        "keywords": [
            "electoral commission", "civil service", "anti-corruption", "oversight body",
            "inspector general", "ombudsman", "regulatory capture", "term limits",
            "checks and balances", "bureaucracy", "career official"
        ],
        "yellow_indicators": [
            "political appointments", "reduce funding", "oversight criticism",
            "bureaucrat criticism", "reform proposal", "term extension"
        ],
        "orange_indicators": [
            "remove watchdogs", "dismantle commission", "fire career officials",
            "political loyalty test", "bypass procedures", "rule by decree"
        ],
        "red_indicators": [
            "eliminate term limits", "disband oversight", "gut civil service",
            "abolish independent bodies", "consolidate power", "direct control"
        ]
    }
}

# Analysis settings
ANALYSIS_INTERVAL_HOURS = 6  # Run analysis every 6 hours