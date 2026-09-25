"""Offline, deterministic beneficiary profile extraction.

Conservative, local-only rules for the full SkillMitra UI language set.
The rules intentionally cover common jury/profile facts (education, livelihood signal,
experience, work preference, location and training willingness) without requiring Ollama.
A local LLM can still enrich genuinely unusual free-form descriptions. Common ASR spelling
variants are included because multilingual speech transcripts are not always dictionary-perfect.
"""
import re
from difflib import SequenceMatcher
from typing import Optional
from backend.nlu.base import ProfileExtractor
from backend.models.beneficiary import BeneficiaryProfile, Experience

TRADE_TERMS = {
    # This vocabulary is deliberately a livelihood-language bridge, not a course map.
    # It lets the deterministic offline fallback canonicalise common English/Hindi/Telugu
    # expressions before the official NQR retriever chooses qualifications.
    "electrical": [
        "electrician", "electrical", "electraction", "electrition", "electrishan", "electrican", "wiring", "wire", "switch", "motor repair", "bijli", "बिजली",
        "इलेक्ट्रिशियन", "इलेक्ट्रीशियन", "इलेक्ट्रिकल", "इलेक्टिकल", "इलेक्टिक", "लेक्टिक",
        "सेलट्रशन", "इलेक्ट्रशन", "इलेक्ट्रेशन", "इलेक्ट्रेसन", "इलेक्टरेशन", "इलेक्ट्रीशन", "इलेक्ट्रिसन", "इलेक्ट्रीसन", "वायरिंग", "तार",
        "ఎలక్ట్రీషియన్", "ఎలక్ట్రిషియన్", "ఎలక్ట్రికల్", "ఎలెక్ట్రీషియన్", "ఇలెక్ట్రీషియన్", "వైరింగ్", "కరెంట్ పని", "కరెంటు పని", "కరెంట్ వర్క్", "ఎలక్ట్రికల్ వర్క్", "ఎలక్ట్రికల్ పని", "ఎలక్ట్రిక్ పని", "లైన్‌మన్", "వైర్‌మన్", "విద్యుత్ పని",
        "எலக்ட்ரீஷியன்", "எலக்ட்ரிஷியன்", "மின்சார வேலை", "வயரிங்",
        "ಎಲೆಕ್ಟ್ರಿಷಿಯನ್", "ವೈರಿಂಗ್", "ವಿದ್ಯುತ್ ಕೆಲಸ",
        "ഇലക്ട്രീഷ്യൻ", "വയറിംഗ്", "വൈദ്യുതി ജോലി",
        "इलेक्ट्रीशियन", "वीज काम",
        "ইলেকট্রিশিয়ান", "ওয়্যারিং", "বিদ্যুৎ কাজ",
        "ઇલેક્ટ્રિશિયન", "વાયરિંગ", "વીજ કામ",
        "ਇਲੈਕਟ੍ਰੀਸ਼ੀਅਨ", "ਵਾਇਰਿੰਗ", "ਬਿਜਲੀ ਦਾ ਕੰਮ",
        "ଇଲେକ୍ଟ୍ରିସିଆନ", "ୱାୟରିଂ", "ବିଦ୍ୟୁତ କାମ",
    ],
    "plumbing": [
        "plumber", "plambar", "plumbing", "pipe fitting", "paip fitting", "pipe repair", "water pipe", "pump repair", "nal", "नल",
        "प्लंबर", "प्लम्बर", "प्लम्बिंग", "पाइप", "पाइप फिटिंग", "पंप रिपेयर",
        "ప్లంబర్", "ప్లంబింగ్", "ప్లంబరు", "ప్లంబింగు", "ప్లంబింగ్ పని", "పైప్ ఫిట్టింగ్", "పైపు పని", "నీటి పైపు", "పంప్ రిపేర్",
        "பிளம்பிங்", "பிளம்பர்", "குழாய் வேலை",
        "ಪ್ಲಂಬಿಂಗ್", "ಪ್ಲಂಬರ್", "ಪೈಪ್ ಕೆಲಸ",
        "പ്ലംബിംഗ്", "പ്ലമ്പർ", "പൈപ്പ് ജോലി",
        "नळ काम",
        "প্লাম্বার", "প্লাম্বিং", "নলের কাজ",
        "પ્લમ્બર", "પ્લમ્બિંગ",
        "ਪਲੰਬਰ", "ਪਲੰਬਿੰਗ",
        "ପ୍ଲମ୍ବର", "ପ୍ଲମ୍ବିଂ", "ପାଇପ୍ କାମ",
    ],
    "masonry": [
        "mason", "masonry", "brick work", "brickwork", "brick laying", "bricklayer", "construction worker", "raj mistry", "eet ka kaam",
        "build houses", "building houses", "house construction", "cement work", "raj mistri", "rajmistri",
        "राजमिस्त्री", "मिस्त्री", "ईंट का काम", "ईंट लगाना", "ईंट लगाता", "ईंट लगाती", "मकान बनाना", "मकान बनाता", "मकान बनाती", "घर बनाना", "निर्माण काम", "सीमेंट का काम",
        "మేస్త్రీ", "మేసన్", "ఇటుక పని", "ఇటుకలు", "ఇల్లు కట్టడం", "ఇళ్ళు కట్టడం", "ఇల్లు కడతాను", "ఇళ్ళు కడతాను", "నిర్మాణ పని",
        "கொத்தனார்", "செங்கல் வேலை", "கட்டிட வேலை", "கட்டுமான வேலை",
        "ಮೇಸ್ತ್ರಿ", "ಇಟ್ಟಿಗೆ ಕೆಲಸ", "ಕಟ್ಟಡ ಕೆಲಸ",
        "മേസ്തിരി", "ഇഷ്ടിക ജോലി", "നിർമാണ ജോലി",
        "गवंडी", "बांधकाम", "विटांचे काम",
        "রাজমিস্ত্রি", "ইটের কাজ", "নির্মাণ কাজ",
        "કડિયો", "ઈંટનું કામ", "બાંધકામ",
        "ਮਿਸਤਰੀ", "ਇੱਟਾਂ ਦਾ ਕੰਮ", "ਉਸਾਰੀ",
        "ରାଜମିସ୍ତ୍ରୀ", "ଇଟା କାମ", "ନିର୍ମାଣ କାମ",
    ],
    "computer hardware": [
        "computer hardware", "hardware", "computer repair", "laptop repair", "network repair", "कंप्यूटर हार्डवेयर", "लैपटॉप रिपेयर",
        "కంప్యూటర్ హార్డ్వేర్", "కంప్యూటర్ రిపేర్", "ల్యాప్టాప్ రిపేర్", "లాప్‌టాప్ రిపేర్",
    ],
    "mobile repair": [
        "mobile repair", "repair mobile", "mobile phones", "repair phones", "phone repair", "smartphone repair", "मोबाइल रिपेयर", "फोन रिपेयर",
        "మొబైల్ రిపేర్", "ఫోన్ రిపేర్", "సెల్ ఫోన్ రిపేర్",
        "மொபைல் ரிப்பேர்", "மொபைல் சர்வீஸ்", "போன் ரிப்பேர்",
        "ಮೊಬೈಲ್ ರಿಪೇರಿ", "ಮೊಬೈಲ್ ಸರ್ವೀಸ್",
        "മൊബൈൽ റിപ്പയർ", "മൊബൈൽ സർവീസ്",
        "मोबाइल रिपेअर", "फोन दुरुस्ती",
        "মোবাইল মেরামত", "মোবাইল রিপেয়ার",
        "મોબાઇલ રીપેરિંગ", "મોબાઇલ રીપેર",
        "ਮੋਬਾਈਲ ਰਿਪੇਅਰ",
        "ମୋବାଇଲ୍ ରିପେୟାର", "ମୋବାଇଲ ରିପେୟାର", "ମୋବାଇଲ ମରାମତି",
    ],
    "carpentry": [
        "carpenter", "carpentry", "wood work", "woodwork", "wooden furniture", "make furniture", "furniture work", "badhai", "बढ़ई", "बढई", "कारपेंटर", "कारपेन्टर", "लकड़ी का काम", "लकड़ी काम", "फर्नीचर काम",
        "కార్పెంటర్", "వడ్రంగి", "చెక్క పని", "ఫర్నిచర్ పని", "కార్పెంటరీ", "కార్పెంటర్ పని",
        "കാർപെന്റർ", "கார்பெண்டர்", "ಕಾರ್ಪೆಂಟರ್", "কার্পেন্টার", "કાર્પેન્ટર", "ਕਾਰਪੇਂਟਰ", "କାର୍ପେଣ୍ଟର",
    ],
    "welding": [
        "welder", "welding", "fabrication", "वेल्डर", "वेल्डिंग", "फैब्रिकेशन", "वेल्डिंग का काम", "वेल्डिंग काम", "వెల్డర్", "వెల్డింగ్", "ఫ్యాబ్రికేషన్", "వెల్డింగ్ పని",
        "வெல்டிங்", "வெல்டர்", "ವೆಲ್ಡಿಂಗ್", "ವೆಲ್ಡರ್", "വെൽഡിംഗ്", "വെൽഡർ",
        "ওয়েল্ডিং", "ওয়েল্ডার", "વેલ્ડિંગ", "વેલ્ડર", "ਵੈਲਡਿੰਗ", "ਵੈਲਡਰ", "ୱେଲଡିଂ", "ୱେଲଡର",
    ],
    "automotive": [
        "mechanic", "meknik", "automobile", "automotive", "bike repair", "bike repairing", "repair bikes", "repairing bikes", "bikes and scooters", "fixing bikes", "fix bikes", "motorcycle repair", "scooter repair", "two wheeler repair", "car repair", "vehicle repair",
        "मैकेनिक", "बाइक रिपेयर", "बाइक ठीक", "मोटरसाइकिल रिपेयर", "मोटरसाइकिल ठीक", "कार रिपेयर", "गाड़ी रिपेयर",
        "మెకానిక్", "బైక్ రిపేర్", "బైక్ మెకానిక్", "మోటార్ సైకిల్ రిపేర్", "కార్ రిపేర్", "వాహనం రిపేర్", "ఆటోమొబైల్", "మెకానిక్ పని", "బైక్ వర్క్",
        "மெக்கானிக்", "பைக் மெக்கானிக்", "வாகன பழுது",
        "ಮೆಕ್ಯಾನಿಕ್", "ಬೈಕ್ ಮೆಕ್ಯಾನಿಕ್",
        "മെക്കാനിക്", "ബൈക്ക് മെക്കാനിക്",
        "मेकॅनिक", "बाईक मेकॅनिक", "गाडी दुरुस्ती",
        "মেকানিক", "বাইক মেকানিক",
        "મિકેનિક", "બાઇક મિકેનિક",
        "ਮਕੈਨਿਕ", "ਬਾਈਕ ਮਕੈਨਿਕ",
        "ମେକାନିକ୍", "ବାଇକ୍ ମେକାନିକ୍",
    ],
    "tailoring": [
        "tailor", "tailoring", "stitch", "stitching", "sewing", "alter clothes", "garment stitching", "silai", "सिलाई", "टेलर", "स्टिचिंग", "कपड़े सिलना", "कपड़े सिलती", "कपड़े सिलता", "सिलाई का काम",
        "టైలర్", "టైలరింగ్", "కుట్టు పని", "బట్టలు కుట్టడం", "బట్టలు కుట్టుతాను", "కుట్టడం", "టైలరింగ్ పని",
        "தையல்", "தையல்காரர்", "டெய்லர்", "தையல் வேலை",
        "ಟೈಲರ್", "ಹೊಲಿಗೆ", "ಹೊಲಿಗೆ ಕೆಲಸ",
        "തയ്യൽ", "ടെയ്‌ലർ", "തയ്യൽ ജോലി",
        "शिंपी", "शिलाई", "कपडे शिवणे",
        "দর্জি", "সেলাই", "টেইলার",
        "દરજી", "સિલાઈ", "ટેલર",
        "ਦਰਜ਼ੀ", "ਸਿਲਾਈ", "ਟੇਲਰ",
        "ଦରଜି", "ସିଲେଇ", "ଟେଲର",
    ],
    "beauty": [
        "beautician", "beauty parlour", "beauty parlor", "salon work", "hair dressing", "makeup artist", "ब्यूटीशियन", "ब्यूटी पार्लर", "सैलून",
        "బ్యూటీషియన్", "బ్యూటీ పార్లర్", "సెలూన్", "మేకప్ పని",
        "ಬ್ಯೂಟಿ ಪಾರ್ಲರ್", "பியூட்டி பார்லர்", "ബ്യൂട്ടി പാർലർ", "বিউটি পার্লার", "બ્યુટી પાર્લર", "ਬਿਊਟੀ ਪਾਰਲਰ", "ବ୍ୟୁଟି ପାର୍ଲର",
    ],
    "solar": [
        "solar installer", "solar installation", "solar panel", "solar pv", "सोलर इंस्टॉलर", "सोलर पैनल",
        "సోలార్ ఇన్‌స్టాలర్", "సోలార్ ప్యానెల్", "సోలార్ పని",
        "சோலார்", "சோலார் பேனல்", "ಸೋಲಾರ್", "ಸೋಲಾರ್ ಪ್ಯಾನೆಲ್",
        "സോളാർ", "സോളാർ പാനൽ", "सोलर", "सोलर पॅनल",
        "সোলার", "সোলার প্যানেল", "સોલાર", "સોલાર પેનલ",
        "ਸੋਲਰ", "ਸੋਲਰ ਪੈਨਲ", "ସୋଲାର", "ସୋଲାର ପ୍ୟାନେଲ",
    ],
    "refrigeration and ac": [
        "ac repair", "acs", "air conditioner repair", "refrigerator repair", "refrigerators", "fridge repair", "frij", "hvac", "एसी रिपेयर", "फ्रिज रिपेयर",
        "ఏసీ రిపేర్", "ఎయిర్ కండిషనర్ రిపేర్", "ఫ్రిజ్ రిపేర్", "రెఫ్రిజిరేటర్ రిపేర్", "ఎయిర్ కండిషనర్", "ఫ్రిజ్", "ఫ్రిడ్జ్", "ac ripair", "frij ac ripair",
    ],
    "cctv": [
        "cctv", "security camera", "surveillance camera", "camera installation", "सीसीटीवी", "कैमरा इंस्टॉलेशन",
        "సీసీటీవీ", "సెక్యూరిటీ కెమెరా", "కెమెరా ఇన్‌స్టాలేషన్",
    ],
    "driving": ["driver", "driving", "delivery driver", "ड्राइवर", "गाड़ी चलाना", "ड्राइविंग", "ड्राइविंग का काम", "డ్రైవర్", "డ్రైవింగ్", "వాహనం నడపడం", "డ్రైవర్ పని"],
    "retail": [
        "salesman", "sales person", "sales", "sales work", "retail", "shop", "shop worker", "store worker", "cashier", "सेल्स", "सेल्समैन", "दुकान में", "दुकान में काम", "कैशियर",
        "సేల్స్‌మన్", "సేల్స్", "రిటైల్", "షాప్", "షాప్ పని", "దుకాణంలో పని", "క్యాషియర్",
    ],
    "housekeeping": [
        "housekeeping", "house keeper", "cleaning work", "cleaner", "हाउसकीपिंग", "सफाई काम", "హౌస్‌కీపింగ్", "క్లీనింగ్ పని", "శుభ్రం చేసే పని",
    ],
    "cooking": [
        "cook", "cooking", "chef", "kitchen work", "रसोइया", "खाना बनाना", "कुक", "వంట", "వంటవాడు", "కుక్", "కిచెన్ పని",
    ],
    "baking": [
        "baker", "bakery", "baking", "बेकर", "बेकरी", "బేకర్", "బేకరీ", "బేకింగ్",
        "বেকারি", "બેકરી", "ਬੇਕਰੀ", "பேக்கரி", "ಬೇಕರಿ", "ബേക്കറി", "ବେକେରୀ",
    ],
    "agriculture": [
        "farmer", "farming", "agriculture", "crop farming", "farm work", "farm", "crops", "crop", "paddy", "vegetables", "kisan", "kheti", "किसान", "खेती", "कृषि", "రైతు", "వ్యవసాయం", "పొలం పని", "పంట పని",
    ],
    "dairy": ["dairy", "milk", "sell milk", "cows", "buffaloes", "take care of cows", "milk production", "cattle rearing", "डेयरी", "दूध का काम", "पशुपालन", "డైరీ", "పాల పని", "పశుపోషణ",
              "டெய்ரி", "பால் பண்ணை", "பால் வேலை", "ಹೈನುಗಾರಿಕೆ", "ಹಾಲಿನ ಕೆಲಸ", "ಡೈರಿ",
              "ഡയറി", "പാൽ ജോലി", "ക്ഷീര", "दुग्ध व्यवसाय", "दूध व्यवसाय",
              "ডেইরি", "দুধের কাজ", "দুগ্ধ", "ડેરી", "દૂધનું કામ",
              "ਡੇਅਰੀ", "ਦੁੱਧ ਦਾ ਕੰਮ", "ଡେୟରୀ", "ଦୁଧ କାମ"],
    "security": ["security guard", "guard duty", "security work", "सिक्योरिटी गार्ड", "गार्ड", "సెక్యూరిటీ గార్డ్", "గార్డ్ పని", "સિક્યોરિટી ગાર્ડ", "செக்யூரிட்டி கார்ட்", "ಸೆಕ್ಯೂರಿಟಿ ಗಾರ್ಡ್", "സെക്യൂരിറ്റി ഗാർഡ്"],
    "warehouse": ["warehouse", "storekeeper", "inventory", "packing", "गोदाम", "स्टोरकीपर", "पैकिंग", "గోదాం", "స్టోర్ కీపర్", "ప్యాకింగ్", "વેરહાઉસ", "વેરહાઉસ પેકિંગ", "വേർഹൗസ്", "ವೇರ್ಹೌಸ್", "ವೇರ್‌ಹೌಸ್", "வேர்ஹவுஸ்", "ওয়ারহাউস", "ਵੇਅਰਹਾਊਸ"],
    "healthcare assistant": [
        "healthcare assistant", "hospital assistant", "patient care", "nursing assistant", "हेल्थकेयर असिस्टेंट", "पेशेंट केयर",
        "హెల్త్‌కేర్ అసిస్టెంట్", "హాస్పిటల్ అసిస్టెంట్", "పేషెంట్ కేర్",
    ],
    "data entry": ["data entry", "computer operator", "typing work", "डेटा एंट्री", "कंप्यूटर ऑपरेटर", "డేటా ఎంట్రీ", "కంప్యూటర్ ఆపరేటర్", "టైపింగ్ పని", "కంప్యూటర్ పని", "కంప్యూటర్ వర్క్", "டேட்டா என்ட்ரி", "கணினி டேட்டா என்ட்ரி", "ಡೇಟಾ ಎಂಟ್ರಿ", "ഡാറ്റ എൻട്രി", "ડેટા એન્ટ્રી", "ਡੇਟਾ ਐਂਟਰੀ", "ଡାଟା ଏଣ୍ଟ୍ରି"],
    "food processing": ["food processing", "food production", "फूड प्रोसेसिंग", "खाद्य प्रसंस्करण", "ఫుడ్ ప్రాసెసింగ్", "ఆహార ప్రాసెసింగ్"],
    "handicrafts": ["handicraft", "handicrafts", "artisan", "craft work", "हस्तशिल्प", "कारीगर", "హస్తకళ", "హస్తకళలు", "కళాకారుడు"],
}


INDIAN_LOCATIONS = {
    "hyderabad": ("Hyderabad", "Telangana"),
    "secunderabad": ("Hyderabad", "Telangana"),
    "warangal": ("Warangal", "Telangana"),
    "karimnagar": ("Karimnagar", "Telangana"),
    "nizamabad": ("Nizamabad", "Telangana"),
    "khammam": ("Khammam", "Telangana"),
    "nalgonda": ("Nalgonda", "Telangana"),
    "rangareddy": ("Rangareddy", "Telangana"),
    "ranga reddy": ("Rangareddy", "Telangana"),
    "medak": ("Medak", "Telangana"),
    "mahabubnagar": ("Mahabubnagar", "Telangana"),
    "adilabad": ("Adilabad", "Telangana"),
    "sangareddy": ("Sangareddy", "Telangana"),
    "siddipet": ("Siddipet", "Telangana"),
    "suryapet": ("Suryapet", "Telangana"),
    "mancherial": ("Mancherial", "Telangana"),
    "jagtial": ("Jagtial", "Telangana"),
    "vijayawada": ("Vijayawada", "Andhra Pradesh"),
    "visakhapatnam": ("Visakhapatnam", "Andhra Pradesh"),
    "vizag": ("Visakhapatnam", "Andhra Pradesh"),
    "guntur": ("Guntur", "Andhra Pradesh"),
    "nellore": ("Nellore", "Andhra Pradesh"),
    "kurnool": ("Kurnool", "Andhra Pradesh"),
    "kadapa": ("Kadapa", "Andhra Pradesh"),
    "rajahmundry": ("East Godavari", "Andhra Pradesh"),
    "kakinada": ("Kakinada", "Andhra Pradesh"),
    "tirupati": ("Tirupati", "Andhra Pradesh"),
    "anantapur": ("Anantapur", "Andhra Pradesh"),
    "chittoor": ("Chittoor", "Andhra Pradesh"),
    "prakasam": ("Prakasam", "Andhra Pradesh"),
    "ongole": ("Prakasam", "Andhra Pradesh"),
    "eluru": ("Eluru", "Andhra Pradesh"),
    "srikakulam": ("Srikakulam", "Andhra Pradesh"),
    "vizianagaram": ("Vizianagaram", "Andhra Pradesh"),
    "delhi": ("Delhi", "Delhi"),
    "new delhi": ("New Delhi", "Delhi"),
    "noida": ("Gautam Buddha Nagar", "Uttar Pradesh"),
    "greater noida": ("Gautam Buddha Nagar", "Uttar Pradesh"),
    "ghaziabad": ("Ghaziabad", "Uttar Pradesh"),
    "gurgaon": ("Gurgaon", "Haryana"),
    "gurugram": ("Gurugram", "Haryana"),
    "faridabad": ("Faridabad", "Haryana"),
    "panipat": ("Panipat", "Haryana"),
    "ambala": ("Ambala", "Haryana"),
    "rohtak": ("Rohtak", "Haryana"),
    "mumbai": ("Mumbai", "Maharashtra"),
    "pune": ("Pune", "Maharashtra"),
    "nagpur": ("Nagpur", "Maharashtra"),
    "nashik": ("Nashik", "Maharashtra"),
    "thane": ("Thane", "Maharashtra"),
    "aurangabad": ("Chhatrapati Sambhajinagar", "Maharashtra"),
    "kolhapur": ("Kolhapur", "Maharashtra"),
    "solapur": ("Solapur", "Maharashtra"),
    "bengaluru": ("Bengaluru", "Karnataka"),
    "bangalore": ("Bengaluru", "Karnataka"),
    "mysuru": ("Mysuru", "Karnataka"),
    "mysore": ("Mysuru", "Karnataka"),
    "mangalore": ("Dakshina Kannada", "Karnataka"),
    "mangaluru": ("Dakshina Kannada", "Karnataka"),
    "hubli": ("Dharwad", "Karnataka"),
    "dharwad": ("Dharwad", "Karnataka"),
    "belgaum": ("Belagavi", "Karnataka"),
    "chennai": ("Chennai", "Tamil Nadu"),
    "coimbatore": ("Coimbatore", "Tamil Nadu"),
    "madurai": ("Madurai", "Tamil Nadu"),
    "salem": ("Salem", "Tamil Nadu"),
    "trichy": ("Tiruchirappalli", "Tamil Nadu"),
    "tirunelveli": ("Tirunelveli", "Tamil Nadu"),
    "erode": ("Erode", "Tamil Nadu"),
    "vellore": ("Vellore", "Tamil Nadu"),
    "kolkata": ("Kolkata", "West Bengal"),
    "howrah": ("Howrah", "West Bengal"),
    "asansol": ("Paschim Bardhaman", "West Bengal"),
    "siliguri": ("Darjeeling", "West Bengal"),
    "patna": ("Patna", "Bihar"),
    "gaya": ("Gaya", "Bihar"),
    "muzaffarpur": ("Muzaffarpur", "Bihar"),
    "bhagalpur": ("Bhagalpur", "Bihar"),
    "lucknow": ("Lucknow", "Uttar Pradesh"),
    "kanpur": ("Kanpur", "Uttar Pradesh"),
    "varanasi": ("Varanasi", "Uttar Pradesh"),
    "agra": ("Agra", "Uttar Pradesh"),
    "meerut": ("Meerut", "Uttar Pradesh"),
    "prayagraj": ("Prayagraj", "Uttar Pradesh"),
    "allahabad": ("Prayagraj", "Uttar Pradesh"),
    "bareilly": ("Bareilly", "Uttar Pradesh"),
    "aligarh": ("Aligarh", "Uttar Pradesh"),
    "gorakhpur": ("Gorakhpur", "Uttar Pradesh"),
    "jhansi": ("Jhansi", "Uttar Pradesh"),
    "mathura": ("Mathura", "Uttar Pradesh"),
    "jaipur": ("Jaipur", "Rajasthan"),
    "jodhpur": ("Jodhpur", "Rajasthan"),
    "kota": ("Kota", "Rajasthan"),
    "bikaner": ("Bikaner", "Rajasthan"),
    "udaipur": ("Udaipur", "Rajasthan"),
    "ajmer": ("Ajmer", "Rajasthan"),
    "bhopal": ("Bhopal", "Madhya Pradesh"),
    "indore": ("Indore", "Madhya Pradesh"),
    "jabalpur": ("Jabalpur", "Madhya Pradesh"),
    "gwalior": ("Gwalior", "Madhya Pradesh"),
    "ujjain": ("Ujjain", "Madhya Pradesh"),
    "ahmedabad": ("Ahmedabad", "Gujarat"),
    "surat": ("Surat", "Gujarat"),
    "vadodara": ("Vadodara", "Gujarat"),
    "rajkot": ("Rajkot", "Gujarat"),
    "bhavnagar": ("Bhavnagar", "Gujarat"),
    "chandigarh": ("Chandigarh", "Chandigarh"),
    "ludhiana": ("Ludhiana", "Punjab"),
    "amritsar": ("Amritsar", "Punjab"),
    "jalandhar": ("Jalandhar", "Punjab"),
    "bhubaneswar": ("Khordha", "Odisha"),
    "cuttack": ("Cuttack", "Odisha"),
    "rourkela": ("Sundargarh", "Odisha"),
    "ranchi": ("Ranchi", "Jharkhand"),
    "jamshedpur": ("East Singhbhum", "Jharkhand"),
    "dhanbad": ("Dhanbad", "Jharkhand"),
    "raipur": ("Raipur", "Chhattisgarh"),
    "bhilai": ("Durg", "Chhattisgarh"),
    "guwahati": ("Kamrup Metropolitan", "Assam"),
    "dehradun": ("Dehradun", "Uttarakhand"),
    "haridwar": ("Haridwar", "Uttarakhand"),
    "kochi": ("Ernakulam", "Kerala"),
    "thiruvananthapuram": ("Thiruvananthapuram", "Kerala"),
    "calicut": ("Kozhikode", "Kerala"),
    # Indic script city variants
    "हैदराबाद": ("Hyderabad", "Telangana"),
    "హైదరాబాద్": ("Hyderabad", "Telangana"),
    "హైదరాబాదు": ("Hyderabad", "Telangana"),
    "ஹைதராபாத்": ("Hyderabad", "Telangana"),
    "ಹೈದರಾಬಾದ್": ("Hyderabad", "Telangana"),
    "ഹൈദരാബാദ്": ("Hyderabad", "Telangana"),
    "হায়দরাবাদ": ("Hyderabad", "Telangana"),
    "હૈદરાબાદ": ("Hyderabad", "Telangana"),
    "ਹੈਦਰਾਬਾਦ": ("Hyderabad", "Telangana"),
    "ହାଇଦ୍ରାବାଦ": ("Hyderabad", "Telangana"),
    "वारंगल": ("Warangal", "Telangana"),
    "వరంగల్": ("Warangal", "Telangana"),
    "करीमनगर": ("Karimnagar", "Telangana"),
    "కరీంనగర్": ("Karimnagar", "Telangana"),
    "నిజామాబాద్": ("Nizamabad", "Telangana"),
    "ఖమ్మం": ("Khammam", "Telangana"),
    "నల్గొండ": ("Nalgonda", "Telangana"),
    "గుంటూరు": ("Guntur", "Andhra Pradesh"),
    "गुंटूर": ("Guntur", "Andhra Pradesh"),
    "విజయవాడ": ("Vijayawada", "Andhra Pradesh"),
    "విశాఖపట్నం": ("Visakhapatnam", "Andhra Pradesh"),
    "వైజాగ్": ("Visakhapatnam", "Andhra Pradesh"),
    "కర్నూలు": ("Kurnool", "Andhra Pradesh"),
    "తిరుపతి": ("Tirupati", "Andhra Pradesh"),
    "అనంతపురం": ("Anantapur", "Andhra Pradesh"),
    "నెల్లూరు": ("Nellore", "Andhra Pradesh"),
    "కడప": ("Kadapa", "Andhra Pradesh"),
    "दिल्ली": ("Delhi", "Delhi"),
    "नई दिल्ली": ("New Delhi", "Delhi"),
    "मुंबई": ("Mumbai", "Maharashtra"),
    "पुणे": ("Pune", "Maharashtra"),
    "नागपुर": ("Nagpur", "Maharashtra"),
    "नासिक": ("Nashik", "Maharashtra"),
    "ठाणे": ("Thane", "Maharashtra"),
    "बेंगलुरु": ("Bengaluru", "Karnataka"),
    "ಬೆಂಗಳೂರು": ("Bengaluru", "Karnataka"),
    "चेन्नई": ("Chennai", "Tamil Nadu"),
    "சென்னை": ("Chennai", "Tamil Nadu"),
    "கோயம்புத்தூர்": ("Coimbatore", "Tamil Nadu"),
    "ಬೆಂಗಳೂರು": ("Bengaluru", "Karnataka"),
    "ಮೈಸೂರು": ("Mysuru", "Karnataka"),
    "കൊച്ചി": ("Ernakulam", "Kerala"),
    "കോഴിക്കോട്": ("Kozhikode", "Kerala"),
    "തിരുവനന്തപുരം": ("Thiruvananthapuram", "Kerala"),
    "कोलकाता": ("Kolkata", "West Bengal"),
    "কলকাতা": ("Kolkata", "West Bengal"),
    "पटना": ("Patna", "Bihar"),
    "गया": ("Gaya", "Bihar"),
    "लखनऊ": ("Lucknow", "Uttar Pradesh"),
    "कानपुर": ("Kanpur", "Uttar Pradesh"),
    "वाराणसी": ("Varanasi", "Uttar Pradesh"),
    "आगरा": ("Agra", "Uttar Pradesh"),
    "मेरठ": ("Meerut", "Uttar Pradesh"),
    "प्रयागराज": ("Prayagraj", "Uttar Pradesh"),
    "जयपुर": ("Jaipur", "Rajasthan"),
    "भोपाल": ("Bhopal", "Madhya Pradesh"),
    "इंदौर": ("Indore", "Madhya Pradesh"),
    "अहमदाबाद": ("Ahmedabad", "Gujarat"),
    "અમદાવાદ": ("Ahmedabad", "Gujarat"),
    "सूरत": ("Surat", "Gujarat"),
    "સુરત": ("Surat", "Gujarat"),
    "चंडीगढ़": ("Chandigarh", "Chandigarh"),
    "ਲੁਧਿਆਣਾ": ("Ludhiana", "Punjab"),
    "लुधियाना": ("Ludhiana", "Punjab"),
    "ਅੰਮ੍ਰਿਤਸਰ": ("Amritsar", "Punjab"),
    "अमृतसर": ("Amritsar", "Punjab"),
    "ଭୁବନେଶ୍ୱର": ("Khordha", "Odisha"),
    "भुवनेश्वर": ("Khordha", "Odisha"),
    "କଟକ": ("Cuttack", "Odisha"),
    "रांची": ("Ranchi", "Jharkhand"),
    "रायपुर": ("Raipur", "Chhattisgarh"),
    "देहरादून": ("Dehradun", "Uttarakhand"),
    # Locative inflected forms
    "पुण्यात": ("Pune", "Maharashtra"),
    "मुंबईत": ("Mumbai", "Maharashtra"),
    "नाशिक": ("Nashik", "Maharashtra"),
    "नाशिकमध्ये": ("Nashik", "Maharashtra"),
    "கோவையில்": ("Coimbatore", "Tamil Nadu"),
    "சென்னையில்": ("Chennai", "Tamil Nadu"),
    "மதுரை": ("Madurai", "Tamil Nadu"),
    "மதுரையில்": ("Madurai", "Tamil Nadu"),
    "ಬೆಂಗಳೂರಿನಲ್ಲಿ": ("Bengaluru", "Karnataka"),
    "ಮೈಸೂರಿನಲ್ಲಿ": ("Mysuru", "Karnataka"),
    "കൊച്ചിയിൽ": ("Ernakulam", "Kerala"),
    "കോഴിക്കോട്ട്": ("Kozhikode", "Kerala"),
    "কলকাতায়": ("Kolkata", "West Bengal"),
    "হাওড়া": ("Howrah", "West Bengal"),
    "হাওড়ায়": ("Howrah", "West Bengal"),
    "વડોદરા": ("Vadodara", "Gujarat"),
    "વડોદરામાં": ("Vadodara", "Gujarat"),
    "અમદાવાદમાં": ("Ahmedabad", "Gujarat"),
    "સુરતમાં": ("Surat", "Gujarat"),
    "ਲੁਧਿਆਣੇ": ("Ludhiana", "Punjab"),
    "ଭୁବନେଶ୍ୱରରେ": ("Khordha", "Odisha"),
}

JOB_WORDS = [
    "job", "naukri", "नौकरी", "जॉब", "जाब", "job chahiye", "जॉब चाहिए", "जब चाही", "जब चाहिए",
    "private job", "govt job", "government job", "company job", "factory job", "office job",
    "want job", "need job", "looking for job", "search job", "prefer job", "job preference",
    "full time job", "do job", "kaam chahiye", "work in company",
    "ఉద్యోగం", "జాబ్", "పని కావాలి", "ఉద్యోగం కావాలి", "జాబ్ కావాలి",
    "வேலை வேண்டும்", "வேலை தேவை", "வேலை செய்ய வேண்டும்", "உத்யோகம்",
    "ಉದ್ಯೋಗ ಬೇಕು", "ಕೆಲಸ ಬೇಕು", "ಉದ್ಯೋಗ", "ಕೆಲಸ",
    "ജോലി വേണം", "ജോലി",
    "नोकरी हवी", "नोकरी पाहिजे", "नोकरी",
    "চাকরি চাই", "চাকরি", "চাকরী",
    "નોકરી જોઈએ", "નોકરી",
    "ਨੌਕਰੀ ਚਾਹੀਦੀ", "ਨੌਕਰੀ",
    "ଚାକିରି ଚାହୁଁଛି", "ଚାକିରି",
]
SELF_WORDS = [
    "self employment", "self-employment", "self employed", "khud ka kaam", "apna kaam", "swarozgar", "swarojgar",
    "own work", "independent work", "freelance", "daily wage", "daily wager",
    "सेल्फ एम्प्लॉयमेंट", "सेल्फ एम्प्लोयमेंट", "सेल्फ अंप्लोयमेंट", "सेल्टे अंप्लोयमेंट", "सेल्ट अंप्लोयमेंट",
    "स्वरोजगार", "खुद का काम", "अपना काम",
    "స్వయం ఉపాధి", "సొంత పని", "నా పని",
    "சுயதொழில்", "சொந்த வேலை", "சொந்த தொழில்", "ಸ್ವಯಂ ಉದ್ಯೋಗ", "ಸ್ವಂತ ಕೆಲಸ",
    "സ്വയംതൊഴിൽ", "സ്വന്തം ജോലി", "स्वयंरोजगार", "स्वतःचे काम",
    "স্বনিয়োজিত", "নিজের কাজ", "સ્વરોજગાર", "પોતાનું કામ",
    "ਸਵੈ-ਰੋਜ਼ਗਾਰ", "ਆਪਣਾ ਕੰਮ", "ସ୍ୱୟଂରୋଜଗାର", "ନିଜ କାମ",
]
BUSINESS_WORDS = [
    "business", "bizness", "vyapar", "dukaan", "shop start", "apna business", "start business",
    "open shop", "open a shop", "own shop", "my own shop", "start shop", "start a shop",
    "open dukan", "open dukaan", "dukaan kholna", "dukan kholna", "dukan lagana", "own enterprise", "start enterprise",
    "बिजनेस", "बिज़नेस", "बिसनेस", "बिस्नेच", "व्यापार", "व्यवसाय", "कारोबार", "दुकान",
    "अपना बिजनेस", "अपना बिसनेस", "अपना बिस्नेच", "बिजनेस शुरू", "बिसनेस शुरू", "बिस्नेच श्रोग",
    "दुकान खोलना", "अपनी दुकान",
    "బిజినెస్", "వ్యాపారం", "సొంత బిజినెస్", "ఓన్ బిజినెస్", "బిజినెస్ స్టార్ట్", "వ్యాపారం ప్రారంభ", "షాప్", "దుకాణం",
    "வியாபாரம்", "சொந்த வியாபாரம்", "கடை", "சொந்த கடை", "ವ್ಯವಹಾರ", "ಸ್ವಂತ ವ್ಯವಹಾರ", "ಅಂಗಡಿ",
    "ബിസിനസ്", "സ്വന്തം ബിസിനസ്", "കട", "സ്വന്തം കട", "व्यवसाय", "स्वतःचा व्यवसाय", "दुकान",
    "ব্যবসা", "নিজের ব্যবসা", "দোকান", "વ્યવસાય", "પોતાનો વ્યવસાય", "દુકાન",
    "ਕਾਰੋਬਾਰ", "ਆਪਣਾ ਕਾਰੋਬਾਰ", "ਦੁਕਾਨ", "ବ୍ୟବସାୟ", "ନିଜ ବ୍ୟବସାୟ", "ଦୋକାନ",
]
TRAINING_YES = [
    "course karna", "training karna", "course chahiye", "training chahiye", "learn course", "take a course", "want training",
    "willing for training", "ready for training", "willing to take training", "willing to train", "training willing",
    "willing to learn", "ready to learn", "ready for course", "willing for course", "interested in training",
    "can attend training", "can take training", "willing to attend", "willing to do", "ready to do",
    "karna chahunga", "karna chaahunga", "karna chahungi", "karunga", "karungi", "haan karunga", "ha karunga",
    "taiyar hu", "taiyaar hu", "seekhna chahta", "seekhna hai", "sikhna hai",
    "करना चाहूंगा", "करना चाहूँगा", "करना चाहुंगा", "करना चाहूंगी", "करना चाहूँगी", "करूंगा", "करूँगा", "करुंगा", "करूंगी", "करूँगी",
    "मैं चाहूंगा", "मैं चाहूँगा", "मैं चाहूंगी", "मैं चाहूँगी", "हाँ मैं चाहूंगा", "हाँ मैं चाहूँगा", "हां मैं चाहूंगा", "हां मैं चाहूँगा", "हा मैं चाहूंगा", "हा मैं चाहूँगा", "हा मैं चाहूंगगा", "हां मैं चाहूंगगा",
    "ट्रेनिंग", "कोर्स", "सीखना चाहता", "सीखना है", "ट्रेनिंग चाहिए", "कोर्स चाहिए", "तैयार हूँ", "तैयार हूं",
    "ٹریننگ", "کورس", "ట్రైనింగ్", "కోర్సు", "చేస్తాను", "తీసుకుంటాను", "నేర్చుకుంటాను", "శిక్షణ కావాలి", "ట్రైనింగ్ కావాలి",
    "సిద్ధంగా ఉన్నా", "సిద్దంగా ఉన్నా", "సిద్ధంగా ఉన్నాను", "సిద్దంగా ఉన్నాను", "సిద్ధం", "రెడీ",
    "தயார்", "தயாராக இருக்கிறேன்", "தயாராக உள்ளேன்", "பயிற்சி வேண்டும்",
    "ಸಿದ್ಧ", "ಸಿದ್ಧನಿದ್ದೇನೆ", "ಸಿದ್ಧವಾಗಿದ್ದೇನೆ", "ತಯಾರಿದ್ದೇನೆ", "ತರಬೇತಿ ಬೇಕು",
    "തയ്യാർ", "തയ്യാറാണ്", "പരിശീലനം വേണം",
    "तयार आहे", "राजी आहे", "प्रशिक्षण हवे",
    "রাজি", "প্রস্তুত", "প্রস্তুত আছি", "প্রশিক্ষণ চাই",
    "તૈયાર છું", "તૈયાર", "તાલીમ જોઈએ",
    "ਤਿਆਰ ਹਾਂ", "ਤਿਆਰ", "ਟ੍ਰੇਨਿੰਗ ਚਾਹੀਦੀ",
    "ପ୍ରସ୍ତୁତ", "ପ୍ରସ୍ତୁତ ଅଛି", "ପ୍ରଶିକ୍ଷଣ ଚାହୁଁଛି",
]
TRAINING_NO = [
    "course nahi", "training nahi", "don't want training", "do not want training", "not willing for training",
    "not interested in training", "no training", "no course", "nahi karunga", "nahi karungi",
    "direct job", "only job", "sirf job", "already trained", "no need training",
    "नहीं करूंगा", "नहीं करूँगा", "नहीं करूंगी", "नहीं करूँगी", "नहीं चाहिए", "ट्रेनिंग नहीं", "कोर्स नहीं",
    "ట్రైనింగ్ వద్దు", "కోర్సు వద్దు", "వద్దు",
    "பயிற்சி வேண்டாம்", "கோர்ஸ் வேண்டாம்", "வேண்டாம்", "ತರಬೇತಿ ಬೇಡ", "ಕೋರ್ಸ್ ಬೇಡ", "ಬೇಡ",
    "പരിശീലനം വേണ്ട", "കോഴ്‌സ് വേണ്ട", "വേണ്ട", "प्रशिक्षण नको", "कोर्स नको", "नको",
    "প্রশিক্ষণ চাই না", "কোর্স চাই না", "চাই না", "તાલીમ નહીં", "કોર્સ નહીં",
    "ਟ੍ਰੇਨਿੰਗ ਨਹੀਂ", "ਕੋਰਸ ਨਹੀਂ", "ਨਹੀਂ", "ପ୍ରଶିକ୍ଷଣ ନାହିଁ", "କୋର୍ସ ନାହିଁ",
]
AFFIRMATIVE_SHORT = {
    "yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay",
    "haan", "han", "ha", "ji", "जी", "हाँ", "हां", "जी हाँ", "जी हां",
    "అవును", "అవునండి", "అవును చేస్తాను", "సరే", "తీసుకుంటాను", "సిద్ధంగా ఉన్నా", "సిద్దంగా ఉన్నా", "సిద్ధంగా ఉన్నాను", "సిద్దంగా ఉన్నాను", "రెడీ",
    "ஆம்", "சரி", "தயார்", "தயாராக இருக்கிறேன்",
    "ಹೌದು", "ಸರಿ", "ಸಿದ್ಧ", "ಸಿದ್ಧವಾಗಿದ್ದೇನೆ", "ತಯಾರಿದ್ದೇನೆ",
    "അതെ", "ശരി", "തയ്യാർ", "തയ്യാറാണ്",
    "हो", "होय", "तयार आहे", "राजी आहे",
    "হ্যাঁ", "হ্যা", "রাজি", "প্রস্তুত",
    "હા", "તૈયાર છું", "તૈયાર",
    "ਹਾਂ", "ਹਾਂ ਜੀ", "ਤਿਆਰ ਹਾਂ", "ਤਿਆਰ",
    "ହଁ", "ପ୍ରସ୍ତୁତ", "ପ୍ରସ୍ତୁତ ଅଛି",
}
NEGATIVE_SHORT = {"no", "n", "nahi", "nahin", "नहीं", "नही", "ना", "இல்லை", "ಬೇಡ", "ಇಲ್ಲ", "ഇല്ല", "വേണ്ട", "नको", "না", "ના", "ਨਹੀਂ", "ନା", "ନାହିଁ"}
NO_EXP = ["no experience", "never worked", "koi experience nahi", "experience nahi", "kabhi kaam nahi", "कोई अनुभव नहीं", "काम नहीं किया", "అనుభవం లేదు", "పని అనుభవం లేదు",
          "அனுபவம் இல்லை", "வேலை அனுபவம் இல்லை", "ಅನುಭವ ಇಲ್ಲ", "ಕೆಲಸದ ಅನುಭವ ಇಲ್ಲ", "അനുഭവം ഇല്ല", "ജോലി പരിചയം ഇല്ല",
          "अनुभव नाही", "कामाचा अनुभव नाही", "অভিজ্ঞতা নেই", "কাজের অভিজ্ঞতা নেই", "અનુભવ નથી", "કામનો અનુભવ નથી",
          "ਤਜਰਬਾ ਨਹੀਂ", "ਕੰਮ ਦਾ ਤਜਰਬਾ ਨਹੀਂ", "ଅନୁଭବ ନାହିଁ", "କାମର ଅନୁଭବ ନାହିଁ"]

NUMBER_WORDS = {
    "one": 1, "ek": 1, "एक": 1,
    "two": 2, "do": 2, "दो": 2,
    "three": 3, "teen": 3, "तीन": 3,
    "four": 4, "char": 4, "chaar": 4, "चार": 4,
    "five": 5, "paanch": 5, "पांच": 5,
    "ఒక": 1, "ఒక్క": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5,
    "ஒரு": 1, "ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5,
    "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5,
    "ഒരു": 1, "ഒന്ന്": 1, "രണ്ട്": 2, "മൂന്ന്": 3, "നാല്": 4, "അഞ്ച്": 5,
    "एक": 1, "दोन": 2, "तीन": 3, "चार": 4, "पाच": 5,
    "এক": 1, "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5,
    "એક": 1, "બે": 2, "ત્રણ": 3, "ચાર": 4, "પાંચ": 5,
    "ਇੱਕ": 1, "ਇਕ": 1, "ਦੋ": 2, "ਤਿੰਨ": 3, "ਚਾਰ": 4, "ਪੰਜ": 5,
    "ଏକ": 1, "ଦୁଇ": 2, "ତିନି": 3, "ଚାରି": 4, "ପାଞ୍ଚ": 5,
}


def _contains_any(text: str, terms) -> bool:
    return any(term in text for term in terms)


# Offline ASR is intentionally allowed to be imperfect.  When the assistant has
# just asked for education, map common phonetic/CTC errors to the small set of
# grade values understood by the NQR eligibility engine.  This is contextual:
# these fuzzy rules are never applied to arbitrary profile sentences.
_NOISY_EDUCATION_VARIANTS = {
    "12th": [
        "12th", "twelfth", "twelth", "twelve class", "12 class",
        "बारहवीं", "बारवी", "ట్వెల్త్", "పన్నెండవ తరగతి",
    ],
    "10th": [
        "10th", "tenth", "tenth class", "ten class", "tend class",
        "tend the glass", "tenth glass", "teninth", "tainth", "teenth",
        "tein", "tend", "tena class",
        "टेंथ", "टेंथ क्लास", "टेन्थ", "टेन्थ क्लास", "टैेंथ",
        "टैेंथ क्लास", "टेनथ क्लास", "दसवीं", "दस्वी", "दशवीं",
        "పదో తరగతి", "పదవ తరగతి", "టెన్త్ క్లాస్",
    ],
    "9th": ["9th", "ninth", "nine class", "9 class", "नौवीं", "నవమ తరగతి"],
    "8th": ["8th", "eighth", "eight class", "8 class", "आठवीं", "ఎనిమిదో తరగతి"],
    "5th": ["5th", "fifth", "five class", "5 class", "पांचवीं"],
}


def _fuzzy_education_level(text: str) -> Optional[str]:
    """Return a canonical grade for a short noisy ASR education answer.

    The threshold is deliberately conservative and this helper is only called
    when education is the currently expected conversational field.
    """
    t = re.sub(r"[^\w\u0900-\u0D7F]+", " ", (text or "").lower(), flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None

    # Very common one-token CTC/phonetic forms observed on the jury laptop.
    direct_tokens = {
        "tein": "10th", "teninth": "10th", "tainth": "10th", "teenth": "10th",
        "टेंथ": "10th", "टेन्थ": "10th", "टैेंथ": "10th", "दस्वी": "10th",
    }
    words = t.split()
    for w in words:
        if w in direct_tokens:
            return direct_tokens[w]

    # Compare short n-grams rather than the full sentence, so answers such as
    # "I have completed my teninth" can still resolve to 10th.
    fragments = {t}
    for n in (1, 2, 3):
        for i in range(0, max(0, len(words) - n + 1)):
            fragments.add(" ".join(words[i:i+n]))

    best_level = None
    best_score = 0.0
    for level, variants in _NOISY_EDUCATION_VARIANTS.items():
        for frag in fragments:
            if len(frag) < 3:
                continue
            for variant in variants:
                score = SequenceMatcher(None, frag, variant).ratio()
                if score > best_score:
                    best_score, best_level = score, level

    # 0.77 accepts "Tend the glass" -> "tenth class" (0.80) and
    # "टैेंथ क्लास" -> "टेंथ क्लास" (>0.9), while remaining narrow
    # because this only runs after the explicit education question.
    return best_level if best_score >= 0.77 else None


_COMMON_INDIAN_ASR_FIXES = [
    (r"\belectrishan\b|\belectrition\b|\belectrisian\b|\belectraction\b|\belectrican\b", "electrician"),
    (r"\bplambar\b|\bplambur\b|\bpipe\s+fittar\b", "plumber"),
    (r"\bmeknik\b|\bmekanic\b|\bmakanic\b", "mechanic"),
    (r"\btwo\s+wilar\b|\b2\s+wilar\b", "two wheeler"),
    (r"\bvelder\b|\bweldor\b|\bwellding\b", "welder"),
    (r"\brajmistry\b|\braj\s+mistri\b", "raj mistri"),
    (r"\bfrij\b", "fridge"),
    (r"\bac\s+ripair\b", "ac repair"),
    (r"\bselft?\s+employment\b|\bself\s+employ\b", "self employment"),
    (r"\b10th\s+passout\b|\b10\s+passout\b", "10th pass"),
    (r"\b12th\s+passout\b|\b12\s+passout\b|\binter\s+passout\b", "12th pass"),
    (r"\byrs\s+exp\b|\byr\s+exp\b|\byears\s+exp\b", "years experience"),
]

_EDUCATION_ASR_FIXES = [
    (r"\btend\s+the\s+glass\b", "tenth class"),
    (r"\btenth\s+glass\b", "tenth class"),
    (r"\bteninth\b|\bteenth\b|\btainth\b", "10th class"),
    (r"\btwelth\b|\btwelveth\b", "12th class"),
]


def _has_other_profile_facts(text: str) -> bool:
    """True if text contains signals outside pure education (trade, exp, loc, pref)."""
    t = text.lower()
    for family, terms in TRADE_TERMS.items():
        if any(term in t for term in terms):
            return True
    if _contains_any(t, JOB_WORDS) or _contains_any(t, BUSINESS_WORDS) or _contains_any(t, SELF_WORDS):
        return True
    for loc_key in INDIAN_LOCATIONS:
        if any(ord(c) > 127 for c in loc_key):
            if loc_key in t:
                return True
        elif f" {loc_key} " in f" {t} ":
            return True
    work_signals = [
        "experience", "worked", "working", "repair", "helper", "अनुभव", "काम कर", "काम किया", "तजुर्बा",
        "అనుభవం", "పని చే", "పని చూ", "వర్క్", "సంవత్సర", "నెలల", "years", "yrs", "months", "saal", "साल",
        "ఏళ్లు", "ఏళ్ళు", "ఏండ్ల", "చేస్తున్న", "చేసాను", "చేశాను", "వచ్చిన", "వచ్చు", "काम आता", "काम किया"
    ]
    if any(s in t for s in work_signals):
        return True
    return False


def normalize_contextual_transcript(text: str, expected_field: Optional[str] = None, language_code: Optional[str] = None) -> str:
    """Canonicalise high-confidence Indian accent phonetic slips and field-specific ASR noise."""
    raw = (text or "").strip()
    if not raw:
        return raw

    # Normalize common Indian accent ASR slips first
    res = raw
    for pat, repl in _COMMON_INDIAN_ASR_FIXES:
        res = re.sub(pat, repl, res, flags=re.IGNORECASE)

    if expected_field != "education":
        return res

    for pat, repl in _EDUCATION_ASR_FIXES:
        res = re.sub(pat, repl, res, flags=re.IGNORECASE)

    # CRITICAL: If the user is telling a story with skills, experience, location, or work preferences,
    # NEVER overwrite or truncate their spoken speech to just an education label!
    if _has_other_profile_facts(res):
        return res

    level = _fuzzy_education_level(res)
    if not level:
        return res
    lang = (language_code or "en").lower().split("-")[0]
    if level == "10th":
        native = {
            "hi": "10वीं कक्षा", "te": "పదో తరగతి", "ta": "10ஆம் வகுப்பு",
            "kn": "10ನೇ ತರಗತಿ", "ml": "10ാം ക്ലാസ്", "mr": "10वी",
            "bn": "10ম শ্রেণি", "gu": "10મું ધોરણ", "pa": "10ਵੀਂ ਕਲਾਸ",
            "or": "10ମ ଶ୍ରେଣୀ", "hinglish": "10th class", "en": "10th class",
        }
        return native.get(lang, "10th class")
    return f"{level} class" if level.endswith("th") else level


def _next_missing_field(profile: Optional[BeneficiaryProfile]) -> Optional[str]:
    """Mirror the conversation priority enough to interpret short answers contextually."""
    if profile is None:
        return None
    if not profile.education.level:
        return "education"
    if not (profile.interests or profile.skills or profile.occupation):
        return "livelihood_signal"
    if not profile.experience:
        return "experience"
    if profile.employment_preference is None:
        return "employment_preference"
    if not (profile.location.district or profile.location.state):
        return "location"
    if profile.training_willingness is None:
        return "training_willingness"
    return None


class LocalProfileExtractor(ProfileExtractor):
    def extract_patch(self, text: str, current_profile: Optional[BeneficiaryProfile] = None,
                      language_code: Optional[str] = None) -> BeneficiaryProfile:
        """Extract only the facts stated in *this* turn.

        Keeping the patch separate from the merged profile lets the hybrid online/offline
        routers tell the difference between 'the rules understood this sentence but it
        repeated an already-known fact' and 'the rules understood nothing'. That
        prevents needless cloud/Ollama calls and removes multi-second loops after users
        repeat answers such as 'I studied 10th'.
        """
        raw = text.strip()
        t = re.sub(r"\s+", " ", raw.lower()).strip()
        p = BeneficiaryProfile()
        if language_code:
            p.language = language_code
        expected = _next_missing_field(current_profile)

        # Education
        edu_patterns = [
            (r"\b(?:post\s*graduat(?:e|ed|ion)|masters?|m\.?tech|m\.?sc|m\.?com|m\.?a|mba|mca)\b|स्नातकोत्तर", "Post Graduate"),
            (r"\b(?:graduat(?:e|ed|ion)|degree|bachelor(?:s)?|b\.?tech|b\.?e|b\.?sc|b\.?com|b\.?a|bba|bca)\b|ग्रेजुएट|स्नातक|గ్రాడ్యుయేట్|பட்டதாரி", "Graduate"),
            (r"\b(?:3\s*year|three\s*year).*?diploma", "3 year Diploma"),
            (r"\b(?:2\s*year|two\s*year).*?diploma", "2 year Diploma"),
            (r"\b(?:diploma|polytechnic)\b|डिप्लोमा|డిప్లొమా|డిప్లోమా", "Diploma"),
            (r"\b(?:iti|i\.t\.i)\b|आईटीआई|ఐటీఐ", "ITI"),
            (r"\b(?:intermediate|inter(?: pass)?|12th|12\s*th|12\s*(?:th\s*)?(?:class|std|standard|kaksha)|12\s*vi|12\s*v|12\s*vee|twelfth|twelve(?:th)?\s+(?:class|std|standard)|class\s+12|plus\s*(?:two|2)|\+2|barha?vi|barahveen|hsc)\b|बारहवीं|12वीं|12वी|ఇంటర్మీడియట్|పన్నెండవ|12వ\s*తరగతి|12(?:ஆம்|ம்)?\s*வகுப்பு|பன்னிரண்டாம்\s*வகுப்பு|12ನೇ\s*ತರಗತಿ|ಹನ್ನೆರಡನೇ\s*ತರಗತಿ|12(?:ാം|ആം)\s*ക്ലാസ്|പന്ത്രണ്ടാം\s*ക്ലാസ്|12वी|बारावी|12শ\s*শ্রেণি|দ্বাদশ\s*শ্রেণি|12મ(?:ું)?\s*ધોરણ|12ਵੀਂ\s*(?:ਕਲਾਸ|ਜਮਾਤ)|12ଶ\s*ଶ୍ରେଣୀ", "12th"),
            (r"\b(?:10th|10\s*th|10\s*(?:th\s*)?(?:class|std|standard|kaksha)|10\s*vi|10\s*v|10\s*vee|tenth|tena|ten(?:th)?\s+(?:class|std|standard)|tena\s+class|class\s+10|dasvi|dasveen|matric(?:ulation)?|ssc)\b|(?:दस|दश)व(?:ी|ीं)(?:\s+कक्षा)?|10\s*वीं|10\s*वी|टेन(?:थ)? क्लास|టెన్త్|పదో తరగతి|పదవ తరగతి|10వ\s*తరగతి|10(?:ஆம்|ம்)?\s*வகுப்பு|பத்தாம்\s*வகுப்பு|10ನೇ\s*ತರಗತಿ|ಹತ್ತನೇ\s*ತರಗತಿ|10(?:ാം|ആം)\s*ക്ലാസ്|പത്തாம்\s*ക്ലാസ്|10वी|दहावी|10ম\s*শ্রেণি|দশম\s*শ্রেণি|10મ(?:ું)?\s*ધોરણ|દસમું\s*ધોરણ|10ਵੀਂ\s*(?:ਕਲਾਸ|ਜਮਾਤ)|ਦਸਵੀਂ|10ମ\s*ଶ୍ରେଣୀ|ଦଶମ\s*ଶ୍ରେଣୀ", "10th"),
            (r"\b(?:9th|9\s*th|9\s*vi|ninth|nine(?:th)?\s+(?:class|std|standard)|class\s+9)\b|9वीं|9వ\s*తరగతి|9(?:ஆம்|ம்)?\s*வகுப்பு|9ನೇ\s*ತರಗತಿ|9(?:ാം|ആം)\s*ക്ലാസ്|9वी|9ম\s*শ্রেণি|9મ(?:ું)?\s*ધોરણ|9ਵੀਂ\s*(?:ਕਲਾਸ|ਜਮਾਤ)|9ମ\s*ଶ୍ରେଣୀ", "9th"),
            (r"\b(?:8th|8\s*th|8\s*vi|eighth|eight(?:h)?\s+(?:class|std|standard)|class\s+8)\b|आठवीं|8वीं|ఎనిమిదో తరగతి|8వ\s*తరగతి|8(?:ஆம்|ம்)?\s*வகுப்பு|எட்டாம்\s*வகுப்பு|8ನೇ\s*ತರಗತಿ|ಎಂಟನೇ\s*ತರಗತಿ|8(?:ാം|ആം)\s*ക്ലാസ്|എട്ടാം\s*ക്ലാസ്|8वी|आठवी|8ম\s*শ্রেণি|অষ্টম\s*শ্রেণি|8મ(?:ું)?\s*ધોરણ|8ਵੀਂ\s*(?:ਕਲਾਸ|ਜਮਾਤ)|ਅੱਠਵੀਂ|8ମ\s*ଶ୍ରେଣୀ|ଅଷ୍ଟମ\s*ଶ୍ରେଣୀ", "8th"),
            (r"\b(?:5th|5\s*th|5\s*vi|fifth|five(?:th)?\s+(?:class|std|standard)|class\s+5)\b|5वीं", "5th"),
        ]
        for pat, level in edu_patterns:
            if re.search(pat, t):
                p.education.level = level
                break

        # Short answers such as "10", "10 class" or "I completed 10" are common
        # immediately after the education question. Interpret them only in that context.
        if not p.education.level and expected == "education":
            contextual_grades = [
                (r"(?<!\d)12(?!\d)(?:\s*(?:th|class|standard|std))?", "12th"),
                (r"(?<!\d)10(?!\d)(?:\s*(?:th|class|standard|std))?", "10th"),
                (r"(?<!\d)9(?!\d)(?:\s*(?:th|class|standard|std))?", "9th"),
                (r"(?<!\d)8(?!\d)(?:\s*(?:th|class|standard|std))?", "8th"),
                (r"(?<!\d)5(?!\d)(?:\s*(?:th|class|standard|std))?", "5th"),
            ]
            for pat, level in contextual_grades:
                if re.search(pat, t):
                    p.education.level = level
                    break
            if not p.education.level:
                p.education.level = _fuzzy_education_level(t)

        if p.education.level:
            if _contains_any(t, ["fail", "failed", "फेल", "अनुत्तीर्ण", "dropout", "drop out", "chhod", "छोड़", "discontinued"]):
                p.education.status = "dropped"
            elif _contains_any(t, ["pass", "passed", "passout", "pass out", "cleared", "complete", "completed", "studied", "finished", "done", "पास", "किया है", "की है", "पढ़ा", "पढ़ा", "पढ़ी", "पढ़ी", "पढ़ चुका", "पढ़ चुका", "పాస్", "పూర్తి", "అయ్యాను", "చదివాను",
                                  "முடித்தேன்", "பாஸ்", "படித்தேன்", "ಪಾಸ್", "ಮುಗಿಸಿದ್ದೇನೆ", "ಓದಿದ್ದೇನೆ",
                                  "പാസായി", "പൂർത്തിയാക്കി", "പഠിച്ചു", "पास आहे", "पास झालो", "पास झाले",
                                  "পাশ করেছি", "পাস করেছি", "પાસ", "ਪਾਸ", "ପାସ୍", "ପାସ"]):
                p.education.status = "passed"
            elif _contains_any(t, ["pursuing", "studying", "padh raha", "padh rahi", "पढ़ रहा", "पढ़ रही", "chal raha", "appearing", "final year", "1st year", "2nd year"]) or re.search(r"\bdoing\s+(?:my\s+)?(?:10th|12th|btech|degree|diploma|graduation|iti|inter|studies|course|college|school)\b", t):
                p.education.status = "pursuing"
            else:
                p.education.status = "passed"

        # Trade/skill signals
        found = []
        for family, terms in TRADE_TERMS.items():
            hits = [term for term in terms if term in t]
            if hits:
                found.append((family, hits))
                # Use canonical family as a stable skill, not noisy STT token.
                if family not in p.skills:
                    p.skills.append(family)

        # Hindi IndicConformer commonly returns near-spellings such as
        # "इलेक्ट्रेशन" for "इलेक्ट्रिशियन".
        if not any(family == "electrical" for family, _ in found):
            workish_hi = bool(re.search(r"(?:काम|करता|करती|कर रहा|कर रही|अनुभव|साल|वायर)", t))
            if workish_hi:
                hindi_tokens = re.findall(r"[\u0900-\u097f]{5,}", t)
                targets = ("इलेक्ट्रिशियन", "इलेक्ट्रीशियन", "इलेक्ट्रिकल")
                fuzzy_hit = next((tok for tok in hindi_tokens
                                  if any(SequenceMatcher(None, tok, target).ratio() >= 0.78 for target in targets)), None)
                if fuzzy_hit:
                    found.append(("electrical", [fuzzy_hit]))
                    if "electrical" not in p.skills:
                        p.skills.append("electrical")

        desire = _contains_any(t, [
            "want", "interested", "interest", "pasand", "banna", "seekhna", "sikhna", "chahiye",
            "पसंद", "बनना", "सीखना", "चाहिए", "करना चाहता", "करना चाहती",
            "ఇష్టం", "చేయాలి", "చేయాలని", "నేర్చుకోవాలి", "కావాలి",
        ])
        if any(f == "cctv" for f, _ in found):
            for family, hits in list(found):
                if family == "electrical" and all(h in {"wiring", "wire", "वायरिंग", "తార", "వైరింగ్"} for h in hits):
                    found.remove((family, hits))
                    if family in p.skills:
                        p.skills.remove(family)

        if desire:
            for family, _ in found:
                if family not in p.interests:
                    p.interests.append(family)

        # Employment preference.
        has_business = _contains_any(t, BUSINESS_WORDS) or bool(re.search(r"\b(?:open\s+(?:a\s+)?shop|own\s+shop|start\s+(?:a\s+)?shop|start\s+(?:a\s+)?business|my\s+own\s+shop|open\s+dukan|dukan\s+kholna|dukaan\s+kholna|apna\s+business|own\s+enterprise|start\s+enterprise)\b", t))
        has_self = _contains_any(t, SELF_WORDS) or bool(re.search(r"\b(?:self\s*[- ]?employment|self\s*[- ]?employed|swarozgar|swarojgar|apna\s+kaam|khud\s+ka\s+kaam|own\s+work|independent\s+work|freelance|daily\s+wage)\b", t))
        has_job = _contains_any(t, JOB_WORDS) or bool(re.search(r"\b(?:private\s+job|govt\s+job|government\s+job|company\s+job|factory\s+job|office\s+job|need\s+job|want\s+job|looking\s+for\s+job|search\s+job|prefer\s+job|job\s+preference|full\s+time\s+job|do\s+job|kaam\s+chahiye|job\s+chahiye)\b", t))
        if has_self:
            p.employment_preference = "self_employment"
        elif has_business:
            p.employment_preference = "business"
        elif has_job:
            p.employment_preference = "job"
        elif expected == "employment_preference":
            if re.search(r"(?:अपना|apna).{0,20}(?:बिज|बिस|business|shop|dukaan)", t):
                p.employment_preference = "business"
            elif re.search(r"(?:self|सेल|स्वरोज|खुद)", t):
                p.employment_preference = "self_employment"
            elif re.search(r"(?:job|जॉब|नौकरी|नोकरी|ఉద్యోగం|జాబ్|வேலை|ಉದ್ಯೋಗ|ಕೆಲಸ|ജോലി|চাকরি|નોકરી|ਨੌਕਰੀ|ଚାକିରି)", t):
                p.employment_preference = "job"

        # Training willingness: Recognize both explicit and natural conversational replies
        compact = re.sub(r"[.!?,;:\-]+", " ", t).strip()
        explicit_no = _contains_any(t, TRAINING_NO) or bool(re.search(
            r"\b(?:not|never|no|don't|dont)\s+(?:willing|ready|interested)\s+(?:for|to\s+take|to\s+do)?\s*(?:training|course)\b"
            r"|\b(?:no|nahi|oddu)\s+(?:training|course)\b"
            r"|\b(?:training|course)\s+(?:nahi|oddu|vendaam|beda|not\s+needed|not\s+required)\b"
            r"|\b(?:direct|only)\s+job\b|सिर्फ\s+नौकरी|ट्रेनिंग\s+नहीं",
            compact
        ))
        explicit_yes = _contains_any(t, TRAINING_YES) or bool(re.search(
            r"\b(?:willing|ready|interested|agree|open|eager|want)\s+(?:for|to\s+take|to\s+do|to\s+join|to\s+attend|to\s+learn)?\s*(?:skill\s+course|training|course|classes|upskilling|skill\s+development)\b"
            r"|\b(?:training|course|classes|upskilling)\s+(?:willing|ready|interested|chahiye|chalega|karna\s+hai|seekhna\s+hai|sikhna\s+hai|karunga|karungi|lena\s+hai)\b"
            r"|(?:training|course).{0,25}(?:taiy?ar|karna|chahiye|ready|willing|interested)"
            r"|ट्रेनिंग.{0,20}(?:तैयार|चाहिए|करना|सीखना)|కోర్సు|ట్రైనింగ్.{0,20}(?:సిద్ధం|కావాలి|నేర్చుకోవాలి|చేయాలి|తీసుకుంటాను|చేస్తాను)",
            compact
        ))

        contextual_yes = False
        contextual_no = False
        if expected == "training_willingness":
            contextual_yes = (
                compact in AFFIRMATIVE_SHORT
                or bool(re.search(
                    r"\b(?:yes|yeah|yep|yup|sure|ok|okay)\b"
                    r"|\b(?:i\s*(?:will|'ll|would|can))\s+(?:take|do|join|attend|learn|try)\b"
                    r"|\b(?:i\s*(?:am|'m))\s+(?:willing|ready|interested)\b"
                    r"|\b(?:willing|ready|interested)\b"
                    r"|సి(?:ద్ధ|ద్ద)ంగా\s+ఉన్నా(?:ను)?|సిద్ధం|రెడీ"
                    r"|தயார்|தயாராக\s+(?:இருக்கிறேன்|உள்ளேன்)"
                    r"|ಸಿದ್ಧ(?:ವಾಗಿದ್ದೇನೆ|ನಿದ್ದೇನೆ)?|ತಯಾರಿದ್ದೇನೆ"
                    r"|തയ്യാർ|തയ്യാറാണ്"
                    r"|तयार\s+आहे|राजी\s+आहे"
                    r"|রাজি|প্রস্তুত(?:\s+আছি)?"
                    r"|તૈયાર(?:\s+છું)?"
                    r"|ਤਿਆਰ(?:\s+ਹਾਂ)?"
                    r"|ପ୍ରସ୍ତୁତ(?:\s+ଅଛି)?",
                    compact,
                ))
            )
            contextual_no = (
                compact in NEGATIVE_SHORT
                or bool(re.search(
                    r"\b(?:no|nope)\b"
                    r"|\b(?:i\s*(?:will|would|do|am|'m))\s+not\b"
                    r"|\b(?:not|never)\s+(?:willing|ready|interested)\b",
                    compact,
                ))
            )

        if explicit_no or contextual_no:
            p.training_willingness = False
        elif explicit_yes or contextual_yes:
            p.training_willingness = True

        # Experience duration: digits, fractions, plus number vocabulary
        duration = None
        year_units = r"(?:years?|yrs?|yr|saal|साल|सालों|बरस|वर्षों|సంవత్సరం|సంవత్సరాలు|సంవత్సరాల|ఏళ్లు|ఏళ్ళు|ఏండ్ల|ఇయర్స్|ఇయర్|வருடம்|வருடங்கள்|ஆண்டு|ஆண்டுகள்|இயர்ஸ்|ವರ್ಷ|ವರ್ಷಗಳು|ಇಯರ್ಸ್|വർഷം|വർഷങ്ങൾ|ഇയേഴ്സ്|वर्ष|वर्षे|इयर्स|इयर|বছর|વર્ષ|ਸਾਲ|ਸਾਲਾਂ|ବର୍ଷ|ବର୍ଷର)"
        month_units = r"(?:months?|mos?|mo|mahine|mahina|महीने|महीना|महीनों|నెల|నెలలు|నెలల|மாதம்|மாதங்கள்|ತಿಂಗಳು|ತಿಂಗಳ|മാസം|മാസങ്ങൾ|महिना|महिने|মাস|મહિનો|મહિના|ਮਹੀਨਾ|ਮਹੀਨੇ|ମାସ)"
        m = re.search(rf"(\d+(?:\.\d+)?)\s*{year_units}", t)
        if m:
            duration = round(float(m.group(1)) * 12)
        else:
            m = re.search(rf"(\d+)\s*{month_units}", t)
            if m:
                duration = int(m.group(1))
        if duration is None:
            if re.search(r"(?:one and (?:a )?half|1\s*(?:and a half|\.5))\s*(?:years?|yrs?|saal)", t):
                duration = 18
            elif re.search(r"(?:two and (?:a )?half|2\s*(?:and a half|\.5))\s*(?:years?|yrs?|saal)", t):
                duration = 30
            elif re.search(r"\b(?:half\s+(?:a\s+)?year|6\s*months?)\b", t):
                duration = 6
        if duration is None:
            for word, n in NUMBER_WORDS.items():
                if re.search(rf"(?<!\w){re.escape(word)}\s*{year_units}(?!\w)", t):
                    duration = n * 12
                    break
                if re.search(rf"(?<!\w){re.escape(word)}\s*{month_units}(?!\w)", t):
                    duration = n
                    break

        work_context = _contains_any(t, ["work", "worked", "working", "experience", "kaam", "काम", "repair", "helper", "कर रहा", "कर रही", "किया", "काम कर रहा", "काम कर रही", "काम किया", "काम आता", "अनुभव है", "तजुर्बा", "एक्सपीरियंस", "పని", "అనుభవం", "చేస్తున్న", "చేశాను", "పని చేశాను", "పని చేసాను", "పని చేస్తున్నాను", "పని చేస్తున్నా", "అనుభవం ఉంది", "అనుభవం వుంది", "ఎక్స్‌పీరియన్స్", "వర్క్ చేసాను", "వర్క్ చేశాను", "చేస్తున్నాను", "చేసాను", "వచ్చిన పని", "పని వచ్చు", "వర్క్",
                                         "வேலை செய்த", "அனுபவம்", "ಕೆಲಸ ಮಾಡ", "ಅನುಭವ", "ജോലി ചെയ്തു", "പരിചയം",
                                         "काम केले", "अनुभव", "কাজ করেছি", "অভিজ্ঞতা", "કામ કર્યું", "અનુભવ",
                                         "ਕੰਮ ਕੀਤਾ", "ਤਜਰਬਾ", "କାମ କରି", "ଅନୁଭବ",
                                         "doing", "handling", "fitter", "technician", "operator"])
        explicit_no_experience = _contains_any(t, NO_EXP) or bool(re.search(r"\b(?:fresher|fresh\s+candidate|no\s+experience|zero\s+experience|never\s+worked|fresher\s+hu|kabhi\s+kaam\s+nahi)\b", t))
        if explicit_no_experience:
            p.experience.append(Experience(domain=None, duration_months=0))
        elif duration is not None or work_context:
            domain = found[0][0] if found else None
            if duration is not None or domain is not None:
                p.experience.append(Experience(domain=domain, duration_months=duration))

        # Location: Dictionary lookup of Indian cities, districts and states first
        loc_found = False
        for loc_key, (dist, st) in INDIAN_LOCATIONS.items():
            if any(ord(c) > 127 for c in loc_key):
                matched = loc_key in t
            else:
                matched = bool(re.search(rf"\b{re.escape(loc_key)}\b", t, re.IGNORECASE))
            if matched:
                p.location.district = dist
                p.location.state = st
                loc_found = True
                break

        if not loc_found:
            loc = re.search(
                r"\b(?:live\s+in|living\s+in|lives\s+in|staying\s+in|stay\s+in|located\s+in|residing\s+in|resident\s+of|based\s+in|"
                r"from|belong\s+to|belongs\s+to|native\s+of|native\s+place|hometown|"
                r"rehta\s+hoon|rehti\s+hoon|mein\s+rehta|mein\s+rehti|रहता\s+हूँ|रहती\s+हूँ|से\s+हूँ|"
                r"nivasistunnanu|lo\s+untanu|nunchi|నుంచి|లో\s+ఉంటాను)\s+([a-zA-Z\u0900-\u0D7F][a-zA-Z\u0900-\u0D7F\s.-]{1,25})",
                t
            )
            if loc:
                candidate = re.split(r"\b(?:and|aur|but|lekin|want|job|with|in|for)\b", loc.group(1))[0].strip(" ,.")
                low_cand = candidate.lower()
                is_invalid = any(stop in low_cand for stop in [
                    "shop", "technician", "repair", "mechanic", "electrician", "training", "course",
                    "college", "school", "company", "work", "job", "class", "experience", "months", "years",
                    "electrical", "plumbing", "solar", "mobile", "hardware"
                ])
                if candidate and not is_invalid and len(candidate) >= 3:
                    p.location.district = candidate.title()

        return p

    def extract(self, text: str, current_profile: Optional[BeneficiaryProfile] = None,
                language_code: Optional[str] = None) -> BeneficiaryProfile:
        patch = self.extract_patch(text, current_profile, language_code)
        if current_profile is None:
            return patch
        # Never mutate the caller-owned conversation state while merely probing a
        # fast path.  A deep copy also makes concurrent/request-local reasoning safer.
        return current_profile.model_copy(deep=True).merge(patch)
