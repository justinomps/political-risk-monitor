import datetime
import logging
import json
import traceback # For more detailed error logging
import os # Import os if using os.environ

# Third-party imports - ensure these are installed (pip install Flask Flask-Login PyMongo Werkzeug)
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import pymongo
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

# Assuming config.py exists and has the necessary variables
try:
    from config import (
        SECRET_KEY,
        MONGODB_URI,
        DATABASE_NAME,
        COLLECTION_ARTICLES,
        COLLECTION_EVENTS,
        COLLECTION_SUMMARIES,
        COLLECTION_USERS,
        CATEGORIES
    )
    config_loaded = True
    # Initialize logger early if config loads
    # Configure logging (ensure it's configured even if config import failed)
    logging.basicConfig(
        level=logging.DEBUG, # Set to DEBUG to see more info during debugging
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('flask_app')
    logger.info("Configuration loaded from config.py")
except ImportError:
     # Initialize logger here if config failed
     logging.basicConfig(
         level=logging.DEBUG, # Set to DEBUG to see more info during debugging
         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
     )
     logger = logging.getLogger('flask_app_fallback')
     logger.warning("config.py not found or missing variables. Using default/dummy values.")
     # Define dummy values to allow app to potentially run with limited functionality
     SECRET_KEY = os.environ.get('SECRET_KEY', 'temporary-secret-key-for-dev') # Use env var fallback
     MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/') # Use env var fallback
     DATABASE_NAME = os.environ.get('DATABASE_NAME', 'political_risk_monitor_db') # Use env var fallback
     COLLECTION_ARTICLES = 'articles'
     COLLECTION_EVENTS = 'events'
     COLLECTION_SUMMARIES = 'summaries'
     COLLECTION_USERS = 'users'
     # Provide a more useful default CATEGORIES structure if possible
     CATEGORIES = {
         'default': {'name': 'Default Category'},
         'cat1': {'name': 'Category 1'},
         'cat2': {'name': 'Category 2'}
     }
     config_loaded = False


# Assuming modules/tracker.py exists
try:
    from modules.tracker import IndicatorTracker
    tracker_loaded = True
    logger.info("IndicatorTracker loaded from modules.")
except ImportError:
     logger.warning("modules/tracker.py not found. Trend analysis features may be limited.")
     # Define a dummy tracker if needed for routes that use it
     class IndicatorTracker:
         def get_category_trends(self, cat_id): return {'trend': 'unknown', 'days_at_current_level': 0, 'history': [], 'name': cat_id}
         def get_threshold_history(self): return []
         def get_confirmed_indicators_count(self): return {'yellow': 0, 'orange': 0, 'red': 0}
         def get_accelerating_categories(self): return []
         def get_alert_level_statistics(self): return {'current_level': 'None', 'history': []}
     tracker_loaded = False


# *** UPDATED Level 1 & 2 ADVICE Data ***
# Structure: level[1-5].fight/flight.persona[individual/family/business].resource[limited/moderate/substantial]
ADVICE_DATA = {
    1: { # Level 1 (Alert) - Increased Awareness
        "flight": {
            "individual": {
                "limited": ["Gather Documentation: Collect/organize essential documents (passport, birth cert, medical, etc.); store digital copies securely (ProtonDrive).", "Research Visa Options: Check requirements for potential destinations (focus on connections, skills); use resources like IOM.", "Build Emergency Savings: Start saving for travel/relocation (aim for 1 month expenses); consider low-fee international accounts (Wise).", "Develop Skills: Enhance portable/in-demand skills (Coursera, edX, LinkedIn Learning).", "Learn Languages: Start learning destination languages (Duolingo, Language Transfer)."],
                "moderate": ["Assess International Job Markets: Research job opportunities abroad in your field (LinkedIn, professional associations).", "Explore Remote Work Options: Investigate remote possibilities for geographic flexibility (Remote OK, We Work Remotely).", "Consider Education Pathways: Explore international education as a potential residency route (Education USA).", "Research Border Procedures: Familiarize with requirements for neighboring countries (docs, questions).", "Begin Building International Networks: Expand professional/personal contacts abroad (LinkedIn, associations)."],
                "substantial": ["Consult Immigration Attorneys: Understand optimal legal pathways in potential destinations (AILA referrals).", "Explore Investment Pathways: Research residency/citizenship by investment (Portugal Golden Visa, Canada Start-up Visa).", "Consider Property Acquisition: Research property in potential destinations (Sotheby's, Christie's International).", "Explore Dual Citizenship: Investigate qualification via ancestry, marriage, etc. (consulate websites).", "Develop Global Banking Relationships: Establish banking in multiple countries (HSBC, Citibank)."]
            },
            "family": {
                "limited": ["Create Family Document Folder: Organize all family docs (passports, birth certs, school/medical records); secure digital backups.", "Research Family Visa Options: Check requirements for destinations (dependent ages, reunification policies - UNHCR, IOM).", "Build Emergency Fund (Family): Save for family transport/initial relocation costs.", "Plan for Children's Education: Research international schools/options abroad (International Schools Database).", "Discuss Age-Appropriate Plans: Talk with children about potential moves (focus on opportunities - Expat Child resources)."],
                "moderate": ["Explore Educational Continuity: Research compatible int'l schools/curricula (IB programs).", "Investigate Healthcare Options: Research systems/insurance abroad (Cigna Global, Allianz).", "Develop Family Language Skills: Engage family in learning destination languages (apps, tutors).", "Research Housing Markets: Look into family-appropriate housing abroad (Numbeo for costs).", "Create Digital Portability: Ensure secure access to family records anywhere (secure cloud storage)."],
                "substantial": ["Consult Family Immigration Attorneys: Engage specialists for family relocation pathways.", "Explore International School Placement: Connect with educational consultants (Educational Consultants Assoc.).", "Consider Educational Property Investment: Research property near quality international schools.", "Plan Tax Strategy: Consult international tax experts for relocation implications (Deloitte, KPMG).", "Establish Healthcare Continuity: Develop relationships with international providers (International SOS)."]
            },
            "business": {
                "limited": ["Research Business Mobility: Investigate portability/markets abroad (World Bank Doing Business reports).", "Explore Online Expansion: Build digital presence (Shopify, Etsy) to reduce location dependence.", "Secure Business Documentation: Organize/backup formation docs, tax records, contracts, IP.", "Research Business Visa Options: Explore entrepreneur/investment visas abroad.", "Begin Digital Transformation: Migrate operations to cloud systems (Google Workspace, Microsoft 365)."],
                "moderate": ["Assess International Expansion: Formally assess market opportunities abroad (export assistance programs).", "Explore Distributed Operations: Research models less dependent on a single location.", "Consult Business Immigration Attorneys: Understand options for relocating business/key personnel.", "Begin International Banking Relationships: Establish business accounts abroad (HSBC, Santander).", "Research Business Structure Options: Investigate optimal international structures (holding companies, subsidiaries)."],
                "substantial": ["Conduct Formal Risk Assessment: Initiate political risk assessment (Control Risks, Eurasia Group).", "Develop Geographic Diversification Strategy: Plan diversification of operations, assets, personnel (McKinsey, BCG).", "Initiate Legal Structure Review: Explore options for international flexibility (Baker McKenzie, DLA Piper).", "Assess Capital Mobility: Evaluate ease of moving capital; identify potential restrictions.", "Begin Talent Mobility Planning: Develop protocols for key personnel relocation (Cartus, SIRVA)."]
            }
        },
        "fight": {
            "individual": {
                "limited": ["Develop Political Literacy: Educate self on institutions, warning signs (Freedom House, ICNL).", "Support Quality Journalism: Subscribe to reputable/investigative news (ProPublica, CIR).", "Join Civic Organizations: Get active locally (League of Women Voters).", "Document Concerning Incidents: Keep secure notes on potential democratic erosion.", "Build Cross-Partisan Relationships: Connect with others committed to democratic principles."],
                "moderate": ["Support Democracy Organizations: Donate/volunteer (ACLU, Common Cause, Brennan Center).", "Develop Specialized Knowledge: Learn about election processes, media literacy, civil liberties law.", "Engage in Local Politics: Attend town halls, contact reps, join committees.", "Build Professional Network for Democracy: Connect with peers focused on democratic values.", "Support Independent Media: Consider memberships, event attendance, pro bono help."],
                "substantial": ["Fund Democratic Infrastructure: Support voter protection, civic education, independent media.", "Leverage Professional Influence: Advocate for democratic values within your organization/field (Business Roundtable).", "Connect with Democracy Experts: Build relationships (attend conferences, symposia).", "Support Legal Defense Funds: Contribute for journalists, whistleblowers, civil rights cases (RCFP).", "Fund Media Literacy Initiatives: Support programs in schools/communities (News Literacy Project)."]
            },
            "family": {
                "limited": ["Develop Family Civic Education: Use resources like iCivics, Center for Civic Education.", "Attend Community Events: Participate as a family (local gov open houses, festivals).", "Create Media Literacy Habits: Teach evaluation of sources, misinformation (Common Sense Media).", "Build Diverse Community Connections: Make friends across demographic groups.", "Develop Family Emergency Plans: Create basic plans, teach resilience age-appropriately."],
                "moderate": ["Support Family-Oriented Civic Programs: Donate/volunteer (YMCA Youth & Gov).", "Engage in School Governance: Participate in PTAs, boards; advocate for civic ed.", "Create Family Service Traditions: Volunteer regularly for community/democratic causes.", "Develop Family Discussion Habits: Talk about current events/civic issues.", "Support Youth Civic Engagement: Encourage participation (Model UN, debate, student gov)."],
                "substantial": ["Fund Family Civic Programs: Support innovative family-based civic engagement.", "Create Community Family Events: Sponsor events bringing diverse families together.", "Support Family-Focused Media: Fund quality content teaching democratic values (PBS).", "Engage in Education Philanthropy: Direct support to strengthen civic ed in schools.", "Create Family Foundation Focus: Add democratic resilience as a funding priority."]
            },
            "business": {
                "limited": ["Adopt Democratic Workplace Practices: Transparency, grievance procedures, inclusion.", "Support Civic Engagement: Provide voting info, flexibility, maybe paid time off.", "Join Business Associations: Participate in local groups advocating rule of law.", "Model Media Literacy: Use factual info in business communications.", "Engage in Local Business Advocacy: Participate in local gov processes fairly."],
                "moderate": ["Develop Democratic Corporate Values: Formalize commitment in mission/policies.", "Support Community Democratic Institutions: Sponsor debates, civic hackathons, forums.", "Create Civic Engagement Programs: Support employee voting, volunteering, matching donations.", "Join Industry Democracy Initiatives: Participate in sector-specific efforts.", "Conduct Ethics Training: Include value of democratic institutions, rule of law."],
                "substantial": ["Establish Corporate Democracy Principles: Publish principles, join pledges.", "Fund Democracy Research: Support academics, think tanks studying resilience.", "Create Government Affairs Principles: Establish ethical lobbying guidelines.", "Support Transparency Initiatives: Fund/participate in anti-corruption efforts (Transparency Int'l).", "Develop Industry Democracy Standards: Lead efforts for sector-wide commitments."]
            }
        }
    },
    2: { # Level 2 (Concern) - Strategic Preparation
        "flight": {
            "individual": {
                "limited": ["Secure Valid Passports: Ensure 18+ months validity; apply for any missing.", "Create Document Backup System: Secure digital (encrypted cloud) & physical copies (trusted contacts).", "Research Border Crossing Requirements: Check specific rules for neighboring countries (transport methods, docs, questions).", "Establish Emergency Contacts Abroad: Verify willingness/capacity of contacts to provide initial help.", "Develop Basic Emergency Fund: Cover transport + 1-2 months basic expenses abroad; keep some portable."],
                "moderate": ["Explore Housing Options Abroad: Research short-term rentals, extended stays, network contacts.", "Investigate Transfer of Credentials: Research recognition process in target countries (contact professional bodies).", "Develop Transportation Plan: Detail methods, routes, checkpoints, alternatives.", "Research Healthcare Options Abroad: Investigate access, insurance, continuity of care.", "Test Financial Access: Make small international transfers/withdrawals; research efficient money movement."],
                "substantial": ["Begin Visa Application Processes: Start applying; consider immigration attorneys.", "Explore International Job Opportunities: Actively search via networks, platforms, recruiters.", "Initiate Asset Diversification: Strategically move assets across jurisdictions (use financial advisors).", "Secure International Insurance: Obtain comprehensive health, life, property policies.", "Establish Legal Representation: Engage lawyers in current & potential destination countries."]
            },
            "family": {
                "limited": ["Secure Family Documentation: Ensure current passports, birth certs, school/medical/custody records.", "Create Family Communication Plan: Detail methods, meeting points, separation protocols; create wallet cards.", "Research Family Entry Requirements: Check visa/entry rules for children (esp. with one parent).", "Prepare Children's Emergency Items: Pack small bags (comfort items, ID); practice using them.", "Establish Emergency Funds (Family): Account for higher family travel/settlement costs."],
                "moderate": ["Research Schools and Childcare Abroad: Contact international schools or consultants.", "Develop Healthcare Transition Plan: Secure medical records, identify providers, ensure medication access.", "Create Family Transportation Strategy: Detail plan considering child needs, border challenges, contingencies.", "Prepare Children Psychologically: Discuss potential changes appropriately (adventure/opportunity focus).", "Test Family Mobility: Take trips to potential destinations if possible."],
                "substantial": ["Begin School Application Processes: Initiate applications for international schools.", "Explore Housing Options Abroad (Family): Research/secure family-suitable housing (schools, healthcare).", "Arrange International Healthcare: Secure comprehensive insurance, establish provider relationships.", "Create Education Continuity Plan: Include tutors, online options, temporary homeschooling.", "Establish Family Support Network Abroad: Develop contacts via expat groups, professional connections."]
            },
            "business": {
                "limited": ["Create Business Continuity Plan: Detail processes, contacts, decision protocols for absence/relocation.", "Secure Business Digital Assets: Backup data, IP, records securely (multiple locations).", "Research Business Visa Requirements: Check entrepreneur/investment visa rules abroad.", "Begin Geographic Diversification: Start building client base in stable regions.", "Identify Business Partners/Successors: Begin discrete contingency discussions."],
                "moderate": ["Develop Legal Protection Strategy: Work with attorneys on asset protection, restructuring.", "Create Leadership Continuity Plan: Detail delegation, cross-border protocols.", "Begin Market Diversification: Accelerate expansion into stable regions.", "Secure Intellectual Property: Ensure multi-jurisdiction registration; secure documentation.", "Establish International Banking (Business): Set up accounts for operational flexibility."],
                "substantial": ["Implement Political Risk Protocols: Activate formal monitoring/mitigation plans.", "Accelerate Geographic Diversification: Implement strategies (operations, supply chains, data, personnel).", "Optimize Corporate Structure: Work with lawyers for jurisdictional flexibility/asset protection.", "Develop Asset Protection Strategy: Create comprehensive plan for physical/IP/financial assets.", "Begin Key Personnel Planning: Identify critical staff; discuss potential relocation."]
            }
        },
        "fight": {
            "individual": {
                "limited": ["Develop Community Organizing Skills: Seek training (Midwest Academy, Highlander Center).", "Strengthen Digital Security: Improve practices (Signal, encrypted email, password managers - EFF resources).", "Expand Political Knowledge: Deepen understanding of democratic vulnerabilities (NDI, IFES).", "Create Deliberate Media Diet: Systematically consume diverse, fact-based news (AllSides).", "Join Election Protection Efforts: Volunteer as poll worker, observer (Election Protection)."],
                "moderate": ["Fund Independent Journalism: Support local accountability reporting (INN affiliates).", "Develop Specific Advocacy Skills: Train in communicating with officials, organizing campaigns (Advocacy Institute).", "Support Legal Monitoring: Contribute to orgs monitoring legal threats to democracy (ACLU).", "Build Focused Networks: Connect with others concerned about democratic erosion.", "Learn Strategic Nonviolence: Study principles/tactics (ICNC, Albert Einstein Institution)."],
                "substantial": ["Fund Democracy Innovation: Support orgs developing new approaches (CDT, CEIR).", "Engage Political Leadership: Use access/influence to discuss democratic norms.", "Support Legal Defense Preparedness: Resource orgs building rapid legal response capacity (Lawyers' Committee).", "Fund Civic Education Expansion: Support quality programs, especially in underserved areas.", "Build Coalition Connections: Facilitate collaboration between pro-democracy groups."]
            },
            "family": {
                "limited": ["Strengthen Family Civic Activities: Increase participation (community forums, local meetings).", "Develop Information Literacy Skills: Help family evaluate sources, identify misinformation (MediaWise).", "Create Family Service Project: Address a community need, build engagement skills (VolunteerMatch).", "Build Neighborhood Connections: Strengthen cross-group ties (block parties, gardens).", "Strengthen Family Resilience: Discuss challenges, practice problem-solving/preparedness."],
                "moderate": ["Support Family Civic Programs: Donate/volunteer (YMCA Youth & Gov).", "Create Youth Mentorship: Connect youth with diverse civic leaders.", "Develop School Democracy Initiatives: Enhance student gov, civic projects.", "Build Intergenerational Programs: Support dialogue/skill-building across age groups.", "Support Family Digital Literacy: Fund/volunteer with programs teaching responsible online engagement."],
                "substantial": ["Fund Major Family Programs: Support innovative family-based civic engagement.", "Create Community Family Spaces: Fund spaces via libraries, parks, community orgs.", "Support Family Policy Advocacy: Fund orgs advocating for policies enabling participation (paid leave).", "Develop Family-Focused Media: Support quality content on democratic values.", "Create Family Philanthropic Strategies: Develop specific plans for supporting democracy."]
            },
            "business": {
                "limited": ["Implement Civic Time Off: Create policies for voting, poll working.", "Create Business Democracy Statement: Publish commitment in mission/values.", "Support Local Accountability Journalism: Advertise/sponsor local investigative news.", "Join Business Democracy Initiatives: Participate (Business for America, Democracy Works).", "Host Community Forums: Offer space for discussions, candidate forums."],
                "moderate": ["Create Employee Civic Program: Comprehensive support (voting info, time off, matching).", "Implement Democracy-Supportive Policies: Review privacy, ethics, hiring.", "Support Election Infrastructure: Offer resources/expertise to local election admin.", "Fund Local Governance Improvements: Support tech modernization, transparency.", "Analyze Supply Chain Democracy Impact: Assess suppliers' connections/impact."],
                "substantial": ["Implement Democracy Impact Assessment: Formal process for business activities.", "Engage Industry Associations: Work for sector-wide commitments to democracy.", "Review Government Relations Practices: Audit lobbying for alignment with values.", "Develop Corporate Democracy Strategy: Integrate support across business functions."]
            }
        }
    },
    # --- Levels 3, 4, 5 remain the same as extracted previously ---
    3: { # Level 3 (Orange) - Active Planning
        "flight": {
            "individual": {
                "limited": ["Prepare comprehensive go-bag (72hr+ essentials, docs, meds, cash).", "Research informal border crossings & risks (iOverlander).", "Join secure comms networks with helpers abroad (diaspora groups).", "Convert some assets to portable forms (cash, gold coins, crypto).", "Develop plausible cover stories for travel (research itineraries)."],
                "moderate": ["Apply for work/student visas in stable countries (digital nomad visas).", "Set up reliable international banking (Wise, Revolut).", "Secure temporary housing abroad (extended stay, Airbnb, networks).", "Pre-position essential supplies in accessible locations (storage units).", "Create redundant comms methods (satellite messenger like Garmin inReach)."],
                "substantial": ["Accelerate second citizenship/residency via investment (Henley & Partners).", "Secure property or long-term rentals abroad.", "Transfer significant assets to secure international holdings (trusts).", "Arrange private transport options if commercial routes close (private aviation).", "Retain crisis management professionals for exit planning (Control Risks)."]
            },
            "family": {
                "limited": ["Pack essential go-bags for each family member (age-appropriate).", "Create detailed reunion plans if separated (multiple meeting points).", "Practice emergency protocols with children appropriately (Save the Children resources).", "Establish simple communication codes for scenarios.", "Research humanitarian organizations assisting families (UNHCR)."],
                "moderate": ["Secure school enrollment for children abroad or research homeschooling.", "Arrange temporary family-suitable housing abroad (safety, schools).", "Transfer medical records; arrange continuing care.", "Develop multiple exit routes suitable for children/elderly.", "Pre-position essential child supplies along potential routes."],
                "substantial": ["Secure housing with privacy/security via relocation services (Crown Relocations).", "Arrange specialized services (education, medical, psych) at destination.", "Consider hiring security consultants for family exit planning (Global Guardian).", "Establish legal guardianship contingencies for separation.", "Create trusts/vehicles to protect family assets internationally (Southpac)."]
            },
            "business": {
                "limited": ["Create legal arrangements for business mgmt in absence (power of attorney).", "Secure critical IP/customer data (international registration, encrypted backups).", "Develop protocols for remote business operation (comms, payments).", "Convert business assets to portable/secure forms (international entities).", "Create communication plans for stakeholders (clients, suppliers, employees)."],
                "moderate": ["Establish secondary operational HQs in safer jurisdictions.", "Create legal structures protecting business continuity (subsidiaries).", "Distribute critical operational knowledge among trusted staff.", "Develop scenarios for asset protection (minor disruption to seizure).", "Create emergency protocols for protecting employees."],
                "substantial": ["Accelerate relocation of critical operations to stable regions (Deloitte, EY).", "Implement robust data security/business continuity (distributed storage).", "Establish clear delegation of authority for disruption scenarios.", "Create tiered employee protection plans (evacuation, benefits).", "Develop crisis communication strategies for all stakeholders (Edelman)."]
            }
        },
        "fight": {
            "individual": {
                "limited": ["Join community resilience networks (Transition Network, Mutual Aid Hub).", "Learn advanced secure communication techniques (Signal, ProtonMail, Tor).", "Document rights violations using verification tools (ProofMode, WITNESS).", "Join/support legal observer programs (National Lawyers Guild).", "Create backup plans for essential services (meds, food, comms)."],
                "moderate": ["Support legal defense funds for civil liberties (ACLU, EFF).", "Join professional advocacy groups promoting rule of law.", "Attend/document public hearings for transparency.", "Build networks with journalists covering democratic concerns.", "Develop civic resistance skills (public speaking, organizing, first aid)."],
                "substantial": ["Fund independent journalism initiatives (ICIJ, ProPublica).", "Support organizations monitoring electoral integrity (Carter Center, IDEA).", "Host discussions with experts on democratic resilience (Freedom House).", "Provide pro-bono professional services to civil society (TrustLaw).", "Fund research on democratic backsliding (V-Dem, Brookings)."]
            },
            "family": {
                "limited": ["Create family info literacy discussions (reliable sources, propaganda).", "Build connections with diverse families for support networks.", "Teach children about historical democratic rights movements.", "Participate in community mutual aid initiatives as a family.", "Discuss/practice digital safety as a family (Common Sense Media)."],
                "moderate": ["Support youth civic engagement organizations (Generation Citizen).", "Join/form parent networks focused on educational freedom (PEN America).", "Monitor/document school board decisions affecting rights.", "Create family plans for participating in community support.", "Develop emergency comms plans with trusted contacts."],
                "substantial": ["Fund programs bringing diverse youth together (Seeds of Peace).", "Support legal challenges to civil liberties restrictions (ACLU).", "Create/support community dialogue spaces across divides.", "Fund independent education initiatives preserving critical thinking.", "Establish foundations focused on democratic principles/civic education."]
            },
            "business": {
                "limited": ["Join business coalitions advocating for rule of law (Chambers of Commerce).", "Create crisis communication plans for political disruption scenarios.", "Build redundancy into critical business functions (payments, data).", "Establish relationships with civil liberties legal advisors.", "Support other local businesses facing political pressure."],
                "moderate": ["Join industry associations advocating for business rights/rule of law.", "Implement robust data protection for customer/business data.", "Create ethical operating guidelines for challenging environments.", "Support employees' non-partisan civic engagement (voting time).", "Develop contingency plans for political interference (legal, comms)."],
                "substantial": ["Advocate for clear rules/transparent governance in business settings.", "Support industry-wide standards for resisting improper influence.", "Fund initiatives promoting business ethics/anti-corruption (Transparency Int'l).", "Develop robust whistleblower protections (EthicsPoint).", "Create international accountability mechanisms for leadership (UN Global Compact)."]
            }
        }
    },
    4: { # Level 4 (Red) - Readiness Stage
        "flight": {
            "individual": {
                "limited": ["Finalize go-bag (docs, meds, cash, comms, $500-1000 cash).", "Relocate closer to exit points/borders if possible.", "Convert remaining assets to portable forms (GoldMoney, Ledger wallets).", "Establish final secure communication protocols (Signal disappearing messages).", "Delete sensitive digital info; secure/wipe digital footprint (Privacytools.io)."],
                "moderate": ["Submit/activate visa/asylum applications via expedited channels (VisaHQ).", "Move funds to easily accessible international accounts (Wise, Revolut).", "Finalize transport to border crossings (backup routes, local drivers).", "Secure temporary housing in first destination country (Blueground).", "Prepare cover stories/documentation for border officials."],
                "substantial": ["Activate emergency extraction services (Global Rescue, Int'l SOS).", "Utilize private transport (chartered flights, security details).", "Access premium visa services via investment/business channels (Henley & Partners).", "Execute asset protection strategies (offshore trusts, int'l institutions).", "Activate pre-arranged legal representation in destination countries."]
            },
            "family": {
                "limited": ["Relocate family to safer temporary locations near borders.", "Ensure all members memorize emergency contacts/meeting points.", "Practice emergency separation protocols.", "Prepare children with age-appropriate explanations (Sesame Street resources).", "Pack essential comfort items for children."],
                "moderate": ["Activate education continuity plans (records, remote learning).", "Arrange secure family-suitable transportation.", "Finalize temporary family-appropriate housing abroad.", "Prepare for psychological impacts of displacement (NCTSN resources).", "Ensure essential medical continuity (records, meds, research options)."],
                "substantial": ["Activate private security services for family protection (Control Risks).", "Utilize private/chartered transport (enhanced security, privacy).", "Finalize specialized service arrangements (education, medical, psych).", "Execute legal arrangements for asset protection (trusts, offshore accounts).", "Activate established support networks in destination countries."]
            },
            "business": {
                "limited": ["Execute business continuity plans for absence (delegate authority).", "Transfer operational control via legal documents.", "Secure/transfer critical business data (encrypted cloud like Tresorit).", "Inform key clients/partners via secure channels (maintain confidence).", "Convert/protect business assets from seizure."],
                "moderate": ["Activate business relocation plans to safer jurisdictions.", "Execute legal protocols protecting business assets (force majeure).", "Implement employee safety measures/possible evacuation (Int'l SOS).", "Secure IP/critical data (int'l protection, redundant storage).", "Activate contingency leadership structure."],
                "substantial": ["Execute comprehensive crisis management protocols (Control Risks, Kroll).", "Activate geographically distributed leadership structure.", "Implement employee protection/evacuation plans (varied risk levels).", "Secure critical data and intellectual property.", "Activate pre-established stakeholder communication strategy."]
            }
        },
        "fight": {
            "individual": {
                "limited": ["Join established community resilience networks.", "Participate in peaceful documentation of rights violations.", "Support underground information networks if media controlled.", "Practice advanced operational security (OPSEC) for communications.", "Connect with international human rights monitors.", "Rely on established emergency supplies/equipment.", "Join neighborhood protection networks.", "Utilize defensive tools/training if necessary.", "Implement full security protocols for daily activities.", "Maintain strict OPSEC in all communications."],
                "moderate": ["Support emergency legal defense initiatives.", "Join professional networks documenting government overreach.", "Support alternative information distribution systems.", "Utilize professional skills to support civil society.", "Connect with international advocacy networks.", "Access cached emergency supplies/equipment.", "Participate in organized community protection efforts.", "Implement full security/counter-surveillance measures.", "Utilize alternative communications networks.", "Support community resilience efforts with resources."],
                "substantial": ["Fund rapid-response legal defense networks.", "Support secure platforms for whistleblowers (SecureDrop).", "Fund emergency journalism initiatives.", "Support international advocacy campaigns.", "Fund documentation of rights violations for future accountability.", "Access secure facilities with long-term sustainability.", "Support community protection networks with resources.", "Deploy private security resources for community protection if necessary.", "Utilize advanced communication/counter-surveillance systems.", "Fund community resilience initiatives for vulnerable populations."]
            },
            "family": {
                "limited": ["Connect with support networks for families under threat.", "Implement family security protocols for communication.", "Support children's psychological resilience.", "Participate in community mutual aid networks.", "Document threats to family safety for accountability."],
                "moderate": ["Support underground educational initiatives if needed.", "Join parent networks advocating for children's safety.", "Utilize professional skills for family protection networks.", "Support youth mental health resources.", "Connect with international family advocacy organizations."],
                "substantial": ["Fund emergency support for families under threat.", "Support legal defense for family rights.", "Fund secure communication networks for vulnerable families.", "Support international advocacy for family protection.", "Fund documentation of family separation/rights violations."]
            },
            "business": {
                "limited": ["Join business networks resisting improper government control.", "Implement maximum data protection/operational security.", "Support employees facing political threats.", "Convert business assets to resist seizure.", "Connect with international business advocacy groups."],
                "moderate": ["Support legal challenges to business interference.", "Implement emergency employee protection measures.", "Utilize business resources to support civil society.", "Activate business continuity plans for scenarios.", "Connect with international business organizations."],
                "substantial": ["Deploy significant resources to legal challenges.", "Implement comprehensive employee protection programs.", "Utilize international business leverage for advocacy.", "Support industry-wide resistance to improper governance.", "Fund documentation of business interference."]
            }
        }
    },
    5: { # Level 5 (Critical) - Immediate Action
        "flight": {
            "individual": {
                "limited": ["Execute immediate departure via safest route.", "Travel ONLY with essential go-bag.", "Use predetermined emergency contacts at destination.", "Follow secure communication protocols (Signal, Briar).", "Seek immediate assistance from humanitarian orgs (UNHCR Help)."],
                "moderate": ["Activate pre-arranged emergency transport.", "Access pre-positioned international funds (Wise, Revolut).", "Move directly to pre-arranged temporary housing.", "Execute digital security protocols (device wiping - iVerify, Wipe).", "Contact pre-arranged legal assistance abroad (IRAP)."],
                "substantial": ["Execute private extraction services (Global Rescue, Int'l SOS).", "Activate high-level diplomatic contacts.", "Utilize premium immigration services upon arrival (Henley & Partners).", "Access emergency funds via secure channels (offshore trusts).", "Implement comprehensive security protocols at destination (Control Risks)."]
            },
            "family": {
                "limited": ["Implement full family emergency evacuation plan (ID bracelets).", "Activate emergency reunion protocols if separated (tracking devices).", "Contact humanitarian assistance immediately (Red Cross, UNHCR).", "Implement simple family communication code words.", "Access emergency shelters or faith-based networks (JRS, HIAS)."],
                "moderate": ["Execute family transportation plan.", "Access emergency family-appropriate housing (Blueground, Sonder).", "Implement secure family comms (satellite messengers).", "Activate education/medical continuity plans.", "Access emergency psychological support (Headspace, NCTSN)."],
                "substantial": ["Deploy private security for family evacuation (GardaWorld).", "Utilize high-level connections for expedited border processing.", "Access comprehensive family support services at destination (Crown Relocations).", "Implement family security protocols at destination (Pinkerton).", "Contact pre-arranged legal representation for family protection (Fragomen)."]
            },
            "business": {
                "limited": ["Execute final business continuity protocol (transfer control).", "Complete final secure backup/transfer of critical data (Tresorit).", "Activate stakeholder communication plan via secure channels.", "Access secured business assets in international locations.", "Establish remote operations capability quickly."],
                "moderate": ["Execute emergency business relocation plan.", "Activate distributed leadership structure.", "Deploy employee evacuation assistance program (Anvil).", "Secure critical assets from seizure (legal structures, transfers).", "Implement crisis communication strategy (Everbridge)."],
                "substantial": ["Activate full crisis management protocol (Kroll).", "Execute comprehensive employee protection measures (Int'l SOS).", "Implement maximum asset protection strategies (force majeure).", "Activate international legal defense (White & Case).", "Execute full stakeholder communication strategy (Kekst CNC)."]
            }
        },
        "fight": {
            "individual": {
                "limited": ["Participate ONLY in established, coordinated peaceful resistance.", "Follow STRICT security protocols (Signal, Briar, Tor).", "Document abuses through secure channels ONLY (ProofMode, eyeWitness).", "Support community mutual aid for vulnerable populations.", "Connect ONLY with trusted underground support networks.", "Rely on prepared emergency supplies.", "Participate in established community protection groups.", "Utilize defensive preparations if necessary.", "Maintain minimal visible profile.", "Help distribute essential supplies."],
                "moderate": ["Support emergency legal defense initiatives (Front Line Defenders).", "Utilize professional skills ONLY through secure channels.", "Support secure communication infrastructure (mesh networks).", "Connect ONLY with trusted international advocacy networks.", "Document abuses for future accountability.", "Deploy cached resources for community support.", "Support organized community defense initiatives.", "Utilize secure facilities/communication methods.", "Coordinate resource distribution.", "Implement full counter-surveillance protocols."],
                "substantial": ["Fund emergency legal defense networks (Civil Rights Defenders).", "Support underground journalism/whistleblowers (SecureDrop).", "Fund secure communication infrastructure.", "Support international monitoring/advocacy.", "Fund evacuation support for those most at risk.", "Deploy significant resources for community protection.", "Access secure facilities with long-term sustainability.", "Support community-wide resilience with stockpiled resources.", "Fund protective measures for at-risk populations.", "Support coordinated resistance through resource provision."]
            },
            "family": {
                "limited": ["Connect with underground family support networks.", "Follow maximum security protocols for all communications.", "Implement family emergency plans (separation, medical, shelter).", "Support community protection of vulnerable families.", "Document family-specific threats through secure channels.", "Utilize prepared emergency supplies.", "Implement family security/protection measures.", "Access community safe houses if necessary.", "Use emergency medical supplies/training.", "Maintain strict OPSEC with children's activities."],
                "moderate": ["Support emergency protection for families under threat (War Child).", "Participate in networks providing alternative education.", "Utilize professional skills ONLY through secure channels.", "Connect with international family advocacy groups.", "Document family rights violations for accountability.", "Deploy cached family emergency supplies.", "Implement comprehensive family security protocols.", "Utilize established safe locations.", "Coordinate with other families for mutual protection.", "Support children's psychological resilience."],
                "substantial": ["Fund emergency extraction for families at extreme risk.", "Support underground education/support networks.", "Fund secure communication for family protection networks.", "Support international advocacy focused on families.", "Fund documentation/future accountability mechanisms.", "Access secure facilities with long-term family sustainability.", "Provide resources for community-wide family protection.", "Deploy private security resources if necessary.", "Support multiple families with emergency resources.", "Create secure educational environments during crisis."]
            },
            "business": {
                "limited": ["Connect ONLY with trusted business resistance networks.", "Implement maximum security for business communications.", "Support employees facing direct threats.", "Utilize business resources ONLY for vetted community needs.", "Document business interference through secure channels."],
                "moderate": ["Support ONLY vetted emergency legal challenges.", "Implement full employee protection protocols.", "Utilize business leverage ONLY through secure channels.", "Join industry-wide resistance efforts.", "Fund documentation of business rights violations."],
                "substantial": ["Deploy maximum resources ONLY to vetted legal challenges.", "Implement comprehensive employee protection.", "Utilize international business relationships ONLY for vetted advocacy.", "Support industry-wide resistance to governance breakdown.", "Fund broad-based civil society support initiatives."]
            }
        }
    }
}
# --- END OF DETAILED ADVICE DICTIONARY ---


# Initialize Flask app
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['TEMPLATES_AUTO_RELOAD'] = True
logger.info("Flask app initialized.")

# Custom filter for datetime formatting
@app.template_filter('datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    """Formats an ISO date string or datetime object."""
    if not value: return ""
    if isinstance(value, str):
        try:
            if value.endswith('Z'): value = value[:-1] + '+00:00'
            value_dt = datetime.datetime.fromisoformat(value)
            return value_dt.strftime(format)
        except ValueError:
            logger.warning(f"Could not parse date string in template filter: {value}")
            return value
    elif isinstance(value, datetime.datetime):
        return value.strftime(format)
    else: return value

# JSON encoder for MongoDB ObjectId and datetime
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId): return str(obj)
        if isinstance(obj, datetime.datetime): return obj.isoformat()
        try: return json.JSONEncoder.default(self, obj)
        except TypeError:
            logger.warning(f"JSONEncoder encountered non-serializable type: {type(obj)}")
            return str(obj)

app.json_encoder = JSONEncoder

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
logger.info("Flask-Login initialized.")

# Database connection
db = None
mongo_client = None
try:
    if not MONGODB_URI: raise ValueError("MONGODB_URI not set.")
    mongo_client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command('ismaster')
    db = mongo_client[DATABASE_NAME]
    logger.info(f"MongoDB connection successful to database '{DATABASE_NAME}'.")
    logger.debug(f"Collections available: {db.list_collection_names()}")
except Exception as e:
     logger.error(f"MongoDB initialization error: {e}")

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.email = user_data.get('email', '')
        self.name = user_data.get('name', 'User')
        self.subscription_level = user_data.get('subscription_level', 'free')
        self.preferences = user_data.get('preferences', {})

@login_manager.user_loader
def load_user(user_id):
    if db is None:
         logger.error("User loader: DB connection not available.")
         return None
    try:
        user_data = db[COLLECTION_USERS].find_one({'_id': ObjectId(user_id)})
        if user_data:
             logger.debug(f"User {user_id} loaded.")
             return User(user_data)
        else:
             logger.warning(f"User ID {user_id} not found.")
             return None
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {e}")
        return None

# --- Routes ---
@app.route('/')
# @login_required
def index():
    logger.info("Accessing dashboard route ('/')")
    if db is None:
         flash("Database connection error.", "danger")
         return render_template("error.html", message="Database connection error."), 503

    summary = None
    try:
        logger.debug(f"Querying '{COLLECTION_SUMMARIES}' for latest summary...")
        summary = db[COLLECTION_SUMMARIES].find_one(sort=[('date', pymongo.DESCENDING)])
        if not summary:
             logger.warning("No summary found. Using default structure.")
             # Create default summary structure if none found
             summary = { # Ensure all keys expected by template exist
                '_id': 'default', 'date': datetime.datetime.now().isoformat(), 'overall_status': 'green',
                'severity_counts_in_period': {'yellow': 0, 'orange': 0, 'red': 0}, 'alert_level': 1,
                'alert_recommendations': ["No summary data available yet."], 'categories': {},
                'thresholds': {'orange_alert_threshold': 3, 'red_alert_threshold': 1, 'orange_threshold_crossed': False, 'red_threshold_crossed': False, 'confirmed_orange_or_red_count': 0, 'confirmed_red_count': 0}
             }
             for cat_id in CATEGORIES:
                 summary['categories'][cat_id] = {'event_count_in_period': 0, 'severity_counts_in_period': {'green': 0, 'yellow': 0, 'orange': 0, 'red': 0}, 'current_severity': 'green', 'is_persistent': False, 'duration_days': 0, 'confirmed': False, 'start_date': None, 'latest_event_date_in_period': None}
        else:
             logger.info(f"Found latest summary dated: {summary.get('date')}")
             # Log category details (optional, can be verbose)
             # logger.debug("--- Summary Category Details ---")
             # ... (logging logic from previous version if desired) ...
             # logger.debug("--- End Summary Category Details ---")

    except Exception as e:
        logger.error(f"Error fetching summary: {e}\n{traceback.format_exc()}")
        flash("Error retrieving dashboard summary data.", "danger")
        summary = { # Minimal error state summary
            '_id': 'error', 'date': datetime.datetime.now().isoformat(), 'overall_status': 'unknown',
            'severity_counts_in_period': {}, 'alert_level': 1, 'alert_recommendations': ["Error loading data."],
            'categories': {}, 'thresholds': {}
         }

    # Get recent events
    recent_events = []
    try:
        logger.debug(f"Querying '{COLLECTION_EVENTS}' for recent events...")
        recent_events = list(db[COLLECTION_EVENTS].find().sort('detected_date', pymongo.DESCENDING).limit(5))
        logger.info(f"Found {len(recent_events)} recent events.")
    except Exception as e:
        logger.error(f"Error fetching recent events: {e}")
        flash("Error retrieving recent events.", "warning")

    # Prepare Timeline Data
    timeline_data = {}
    try:
        logger.debug("Preparing timeline data...")
        end_date = datetime.datetime.now()
        start_date = (end_date - datetime.timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        dates = [(start_date + datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        counts_by_date = {date: {'yellow': 0, 'orange': 0, 'red': 0} for date in dates}
        events_in_range = list(db[COLLECTION_EVENTS].find({'detected_date': {'$gte': start_date.isoformat(), '$lte': end_date.isoformat()}}))
        logger.info(f"Found {len(events_in_range)} events for timeline.")
        for event in events_in_range:
            try:
                detected_date_str = event.get('detected_date')
                if not detected_date_str: continue
                if detected_date_str.endswith('Z'): detected_date_str = detected_date_str[:-1] + '+00:00'
                event_dt = datetime.datetime.fromisoformat(detected_date_str)
                event_date_ymd = event_dt.strftime('%Y-%m-%d')
                if event_date_ymd in counts_by_date:
                    severity = event.get('severity')
                    if severity in counts_by_date[event_date_ymd]:
                        counts_by_date[event_date_ymd][severity] += 1
            except Exception as parse_err:
                 logger.warning(f"Skipping event in timeline due to error: {parse_err} - Event: {event.get('_id')}")
        timeline_data = {
            'dates': dates,
            'yellow': [counts_by_date[d]['yellow'] for d in dates],
            'orange': [counts_by_date[d]['orange'] for d in dates],
            'red': [counts_by_date[d]['red'] for d in dates]
        }
        logger.debug(f"Timeline data prepared: {timeline_data}")
    except Exception as e:
        logger.error(f"Error preparing timeline data: {e}\n{traceback.format_exc()}")
        flash("Error generating timeline data.", "warning")
        timeline_data = {} # Ensure empty dict on error

    # Render the template
    logger.debug("Rendering dashboard.html template...")
    try:
        # *** Pass DETAILED advice data to template ***
        # Use the name 'advice_data' to match the updated template
        return render_template(
            'dashboard.html',
            summary=summary,
            recent_events=recent_events,
            categories=CATEGORIES,
            timeline_data=timeline_data,
            advice_data=ADVICE_DATA # Pass the detailed advice dictionary
        )
    except Exception as render_err:
         logger.error(f"Error rendering dashboard template: {render_err}\n{traceback.format_exc()}")
         return render_template("error.html", message="Error rendering dashboard."), 500


# --- Other Routes (Keep them as they were in app_py_fix_db_check, ensuring db is None checks) ---

@app.route('/events')
# @login_required # Add if needed
def events():
    """Displays a filterable list of events."""
    if db is None:
         flash("Database connection error.", "danger")
         return render_template("error.html", message="Database connection error."), 503
    category = request.args.get('category')
    severity = request.args.get('severity')
    page = request.args.get('page', 1, type=int)
    per_page = 25
    query = {}
    if category: query['category'] = category
    if severity: query['severity'] = severity
    events_list = []
    total_events = 0
    try:
        total_events = db[COLLECTION_EVENTS].count_documents(query)
        events_cursor = db[COLLECTION_EVENTS].find(query)\
                                             .sort('detected_date', pymongo.DESCENDING)\
                                             .skip((page - 1) * per_page)\
                                             .limit(per_page)
        events_list = list(events_cursor)
    except Exception as e: logger.error(f"Error fetching events: {e}")
    total_pages = (total_events + per_page - 1) // per_page if per_page > 0 else 0
    return render_template('events.html', events=events_list, categories=CATEGORIES, selected_category=category, selected_severity=severity, current_page=page, total_pages=total_pages)


@app.route('/event/<event_id>')
# @login_required # Add if needed
def event_detail(event_id):
    """Displays details for a single event."""
    if db is None:
         flash("Database connection error.", "danger")
         return render_template("error.html", message="Database connection error."), 503
    event = None
    article = None
    try:
        event = db[COLLECTION_EVENTS].find_one({'_id': ObjectId(event_id)})
        if not event:
            flash('Event not found', 'danger')
            return redirect(url_for('events'))
        article_id_val = event.get('article_id')
        if article_id_val:
             try:
                  article_obj_id = article_id_val if isinstance(article_id_val, ObjectId) else ObjectId(str(article_id_val))
                  article = db[COLLECTION_ARTICLES].find_one({'_id': article_obj_id})
             except Exception as article_err: logger.warning(f"Could not find article {article_id_val}: {article_err}")
    except Exception as e:
         logger.error(f"Error fetching event detail {event_id}: {e}")
         flash('Error retrieving event details.', 'danger')
         return redirect(url_for('events'))
    return render_template('event_detail.html', event=event, article=article, categories=CATEGORIES)


@app.route('/trends')
# @login_required # Add if needed
def trends():
    """Display trend analysis and visualization."""
    if db is None or not tracker_loaded:
         missing = ["database connection"] if db is None else []
         if not tracker_loaded: missing.append("tracker module")
         flash(f"Trend analysis unavailable due to missing components: {', '.join(missing)}.", "danger")
         return render_template("error.html", message="Trend analysis unavailable."), 503
    try:
        tracker = IndicatorTracker()
        category_trends = {}
        for cat_id, cat_config in CATEGORIES.items():
            trend_data = tracker.get_category_trends(cat_id)
            trend_data['name'] = cat_config.get('name', cat_id)
            category_trends[cat_id] = trend_data
        threshold_history = tracker.get_threshold_history()
        confirmed_counts = tracker.get_confirmed_indicators_count()
        accelerating_categories = tracker.get_accelerating_categories()
        alert_statistics = tracker.get_alert_level_statistics()
        current_alert_level = alert_statistics.get('current_level', 'None')
        return render_template('trends.html', category_trends=category_trends, threshold_history=threshold_history, confirmed_counts=confirmed_counts, accelerating_categories=accelerating_categories, alert_statistics=alert_statistics, current_alert_level=current_alert_level, categories=CATEGORIES)
    except Exception as e:
        logger.error(f"Error generating trends page: {e}\n{traceback.format_exc()}")
        flash("Error loading trend data.", "danger")
        return render_template("error.html", message="Error loading trend data."), 500


# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if db is None:
         flash("Database error. Login unavailable.", "danger")
         return render_template('login.html'), 503
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
             flash('Email and password required.', 'warning')
             return render_template('login.html')
        try:
            user_data = db[COLLECTION_USERS].find_one({'email': email})
            if user_data and check_password_hash(user_data.get('password', ''), password):
                user = User(user_data)
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else: flash('Invalid email or password.', 'danger')
        except Exception as e:
             logger.error(f"Login error for {email}: {e}")
             flash('Login error. Please try again.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if db is None:
         flash("Database error. Registration unavailable.", "danger")
         return render_template('register.html'), 503
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        if not email or not password or not name:
             flash('All fields are required.', 'warning')
             return render_template('register.html')
        try:
            if db[COLLECTION_USERS].find_one({'email': email}):
                flash('Email already registered.', 'warning')
                return render_template('register.html')
            user_data = {'_id': ObjectId(), 'email': email, 'password': generate_password_hash(password), 'name': name, 'subscription_level': 'free', 'created_at': datetime.datetime.now().isoformat(), 'preferences': {'alerts_enabled': True, 'alert_threshold': 'orange'}}
            db[COLLECTION_USERS].insert_one(user_data)
            user = User(user_data)
            login_user(user)
            flash('Account created successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
             logger.error(f"Registration error for {email}: {e}")
             flash('Registration error. Please try again.', 'danger')
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/about')
def about():
    return render_template('about.html')


# --- API Endpoints ---
@app.route('/api/summary')
def api_summary():
    if db is None: return jsonify({'error': 'Database error'}), 503
    try:
        summary = db[COLLECTION_SUMMARIES].find_one(sort=[('date', pymongo.DESCENDING)])
        if not summary: return jsonify({'error': 'No summary available'}), 404
        return jsonify(summary)
    except Exception as e:
         logger.error(f"Error in /api/summary: {e}")
         return jsonify({'error': 'Failed to retrieve summary'}), 500


@app.route('/api/events')
def api_events():
    if db is None: return jsonify({'error': 'Database error'}), 503
    try:
        limit = max(1, min(request.args.get('limit', 10, type=int), 100))
        query = {}
        if category := request.args.get('category'): query['category'] = category
        if severity := request.args.get('severity'): query['severity'] = severity
        events = list(db[COLLECTION_EVENTS].find(query).sort('detected_date', pymongo.DESCENDING).limit(limit))
        return jsonify(events)
    except Exception as e:
         logger.error(f"Error in /api/events: {e}")
         return jsonify({'error': 'Failed to retrieve events'}), 500


# --- Application Runner ---
if __name__ == '__main__':
    if not config_loaded: logger.warning("Running with default/dummy config.")
    if db is None:
        logger.critical("DB connection failed. Aborting.")
        exit(1)
    logger.info("Starting Flask development server...")
    # Set host='0.0.0.0' to make it accessible on your network if needed
    # Use port other than default 5000 if necessary
    # Use use_reloader=False if debugging causes issues with reloading or the OSError persists
    app.run(debug=True, host='127.0.0.1', port=5000) #, use_reloader=False)

