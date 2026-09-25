"""Deterministic counter-question selection. No LLM is required."""
from typing import Optional
from backend.models.beneficiary import BeneficiaryProfile
from backend.conversation.completeness import ProfileCompletenessChecker

SUPPORTED_LANGUAGES = {"en", "hi", "hinglish", "te", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "or"}

QUESTIONS = {
    "education": {
        "en": "What is the highest class or qualification you completed?",
        "hi": "आपने सबसे ऊँची कौन-सी कक्षा या योग्यता पूरी की है?",
        "hinglish": "Aapne sabse zyada kaunsi class ya qualification complete ki hai?",
        "te": "మీరు పూర్తి చేసిన అత్యున్నత తరగతి లేదా అర్హత ఏది?",
        "ta": "நீங்கள் முடித்த உயர்ந்த வகுப்பு அல்லது கல்வித் தகுதி என்ன?",
        "kn": "ನೀವು ಪೂರ್ಣಗೊಳಿಸಿದ ಅತಿ ಉನ್ನತ ತರಗತಿ ಅಥವಾ ವಿದ್ಯಾರ್ಹತೆ ಯಾವುದು?",
        "ml": "നിങ്ങൾ പൂർത്തിയാക്കിയ ഏറ്റവും ഉയർന്ന ക്ലാസ് അല്ലെങ്കിൽ വിദ്യാഭ്യാസ യോഗ്യത ഏതാണ്?",
        "mr": "तुम्ही पूर्ण केलेली सर्वात उच्च इयत्ता किंवा शैक्षणिक पात्रता कोणती?",
        "bn": "আপনি সর্বোচ্চ কোন শ্রেণি বা শিক্ষাগত যোগ্যতা সম্পন্ন করেছেন?",
        "gu": "તમે પૂર્ણ કરેલું સૌથી ઊંચું ધોરણ અથવા શૈક્ષણિક લાયકાત કઈ છે?",
        "pa": "ਤੁਸੀਂ ਸਭ ਤੋਂ ਉੱਚੀ ਕਿਹੜੀ ਕਲਾਸ ਜਾਂ ਵਿਦਿਅਕ ਯੋਗਤਾ ਪੂਰੀ ਕੀਤੀ ਹੈ?",
        "or": "ଆପଣ ସମ୍ପୂର୍ଣ୍ଣ କରିଥିବା ସର୍ବୋଚ୍ଚ ଶ୍ରେଣୀ କିମ୍ବା ଶିକ୍ଷାଗତ ଯୋଗ୍ୟତା କଣ?",
    },
    "livelihood_signal": {
        "en": "What kind of work are you interested in, or what work or skills do you already know?",
        "hi": "आप किस तरह का काम करना चाहते हैं, या आपको पहले से कौन-सा काम या कौशल आता है?",
        "hinglish": "Aap kis tarah ka kaam karna chahte hain, ya aapko pehle se kaunsa kaam ya skill aata hai?",
        "te": "మీకు ఏ పని చేయాలని ఉంది, లేదా ఇప్పటికే ఏ పని లేదా నైపుణ్యం తెలుసు?",
        "ta": "நீங்கள் எந்த வேலை செய்ய விரும்புகிறீர்கள், அல்லது ஏற்கனவே எந்த வேலை அல்லது திறன் தெரியும்?",
        "kn": "ನೀವು ಯಾವ ರೀತಿಯ ಕೆಲಸ ಮಾಡಲು ಬಯಸುತ್ತೀರಿ, ಅಥವಾ ಈಗಾಗಲೇ ಯಾವ ಕೆಲಸ ಅಥವಾ ಕೌಶಲ್ಯ ನಿಮಗೆ ಗೊತ್ತಿದೆ?",
        "ml": "നിങ്ങൾക്ക് ഏത് തരത്തിലുള്ള ജോലി ചെയ്യാനാണ് താൽപര്യം, അല്ലെങ്കിൽ ഇതിനകം ഏത് ജോലി/കഴിവാണ് അറിയുന്നത്?",
        "mr": "तुम्हाला कोणत्या प्रकारचे काम करायचे आहे, किंवा तुम्हाला आधीपासून कोणते काम किंवा कौशल्य येते?",
        "bn": "আপনি কী ধরনের কাজ করতে চান, অথবা আগে থেকেই কোন কাজ বা দক্ষতা জানেন?",
        "gu": "તમે કયા પ્રકારનું કામ કરવા માંગો છો, અથવા તમને પહેલેથી કયું કામ કે કુશળતા આવડે છે?",
        "pa": "ਤੁਸੀਂ ਕਿਹੜੇ ਤਰ੍ਹਾਂ ਦਾ ਕੰਮ ਕਰਨਾ ਚਾਹੁੰਦੇ ਹੋ, ਜਾਂ ਤੁਹਾਨੂੰ ਪਹਿਲਾਂ ਤੋਂ ਕਿਹੜਾ ਕੰਮ ਜਾਂ ਹੁਨਰ ਆਉਂਦਾ ਹੈ?",
        "or": "ଆପଣ କେଉଁ ପ୍ରକାର କାମ କରିବାକୁ ଚାହୁଁଛନ୍ତି, କିମ୍ବା ପୂର୍ବରୁ କେଉଁ କାମ କିମ୍ବା କୌଶଳ ଜାଣନ୍ତି?",
    },
    "experience": {
        "en": "Do you have any work experience? If yes, what work did you do and for how long?",
        "hi": "क्या आपको काम का कोई अनुभव है? अगर हाँ, कौन-सा काम और कितने समय तक?",
        "hinglish": "Kya aapko koi kaam ka experience hai? Agar haan, kaunsa kaam aur kitne samay tak?",
        "te": "మీకు పని అనుభవం ఉందా? ఉంటే ఏ పని, ఎంతకాలం చేశారు?",
        "ta": "உங்களுக்கு வேலை அனுபவம் உள்ளதா? இருந்தால் எந்த வேலை, எவ்வளவு காலம் செய்தீர்கள்?",
        "kn": "ನಿಮಗೆ ಕೆಲಸದ ಅನುಭವ ಇದೆಯೇ? ಇದ್ದರೆ ಯಾವ ಕೆಲಸವನ್ನು ಎಷ್ಟು ಕಾಲ ಮಾಡಿದ್ದೀರಿ?",
        "ml": "നിങ്ങൾക്ക് ജോലി പരിചയം ഉണ്ടോ? ഉണ്ടെങ്കിൽ ഏത് ജോലി, എത്രകാലം ചെയ്തു?",
        "mr": "तुम्हाला कामाचा अनुभव आहे का? असल्यास कोणते काम आणि किती काळ केले?",
        "bn": "আপনার কি কাজের অভিজ্ঞতা আছে? থাকলে কী কাজ করেছেন এবং কতদিন?",
        "gu": "તમને કામનો અનુભવ છે? હોય તો કયું કામ અને કેટલા સમય સુધી કર્યું?",
        "pa": "ਕੀ ਤੁਹਾਡੇ ਕੋਲ ਕੰਮ ਦਾ ਤਜਰਬਾ ਹੈ? ਜੇ ਹਾਂ, ਕਿਹੜਾ ਕੰਮ ਅਤੇ ਕਿੰਨੇ ਸਮੇਂ ਲਈ ਕੀਤਾ?",
        "or": "ଆପଣଙ୍କ ପାଖରେ କାମର ଅନୁଭବ ଅଛି କି? ଥିଲେ କେଉଁ କାମ ଏବଂ କେତେ ସମୟ କରିଛନ୍ତି?",
    },
    "employment_preference": {
        "en": "Are you mainly looking for a job, self-employment, or to start a business?",
        "hi": "सिर्फ एक विकल्प बताइए: नौकरी, स्वरोज़गार, या अपना बिजनेस?",
        "hinglish": "Sirf ek option boliye: naukri/job, self-employment, ya apna business?",
        "te": "మీరు ఉద్యోగం, స్వయం ఉపాధి, లేదా మీ స్వంత వ్యాపారం ప్రారంభించాలని అనుకుంటున్నారా?",
        "ta": "நீங்கள் முக்கியமாக வேலை, சுயதொழில், அல்லது சொந்த வியாபாரம் தொடங்க விரும்புகிறீர்களா?",
        "kn": "ನೀವು ಮುಖ್ಯವಾಗಿ ಉದ್ಯೋಗ, ಸ್ವಯಂ ಉದ್ಯೋಗ, ಅಥವಾ ನಿಮ್ಮದೇ ವ್ಯವಹಾರ ಆರಂಭಿಸಲು ಬಯಸುತ್ತೀರಾ?",
        "ml": "നിങ്ങൾ പ്രധാനമായി ജോലി, സ്വയംതൊഴിൽ, അല്ലെങ്കിൽ സ്വന്തം ബിസിനസ് തുടങ്ങാനാണോ ആഗ്രഹിക്കുന്നത്?",
        "mr": "तुम्हाला मुख्यतः नोकरी, स्वयंरोजगार की स्वतःचा व्यवसाय सुरू करायचा आहे?",
        "bn": "আপনি মূলত চাকরি, স্বনিয়োজিত কাজ, নাকি নিজের ব্যবসা শুরু করতে চান?",
        "gu": "તમે મુખ્યત્વે નોકરી, સ્વરોજગાર કે પોતાનો વ્યવસાય શરૂ કરવા માંગો છો?",
        "pa": "ਤੁਸੀਂ ਮੁੱਖ ਤੌਰ 'ਤੇ ਨੌਕਰੀ, ਸਵੈ-ਰੋਜ਼ਗਾਰ ਜਾਂ ਆਪਣਾ ਕਾਰੋਬਾਰ ਸ਼ੁਰੂ ਕਰਨਾ ਚਾਹੁੰਦੇ ਹੋ?",
        "or": "ଆପଣ ମୁଖ୍ୟତଃ ଚାକିରି, ସ୍ୱୟଂରୋଜଗାର କିମ୍ବା ନିଜ ବ୍ୟବସାୟ ଆରମ୍ଭ କରିବାକୁ ଚାହୁଁଛନ୍ତି?",
    },
    "location": {
        "en": "Which district or area do you live in?",
        "hi": "आप किस जिले या क्षेत्र में रहते हैं?",
        "hinglish": "Aap kis district ya area mein rehte hain?",
        "te": "మీరు ఏ జిల్లా లేదా ప్రాంతంలో ఉంటున్నారు?",
        "ta": "நீங்கள் எந்த மாவட்டம் அல்லது பகுதியில் வசிக்கிறீர்கள்?",
        "kn": "ನೀವು ಯಾವ ಜಿಲ್ಲೆ ಅಥವಾ ಪ್ರದೇಶದಲ್ಲಿ ವಾಸಿಸುತ್ತೀರಿ?",
        "ml": "നിങ്ങൾ ഏത് ജില്ലയിലോ പ്രദേശത്തിലോ താമസിക്കുന്നു?",
        "mr": "तुम्ही कोणत्या जिल्ह्यात किंवा भागात राहता?",
        "bn": "আপনি কোন জেলা বা এলাকায় থাকেন?",
        "gu": "તમે કયા જિલ્લા અથવા વિસ્તારમાં રહો છો?",
        "pa": "ਤੁਸੀਂ ਕਿਹੜੇ ਜ਼ਿਲ੍ਹੇ ਜਾਂ ਇਲਾਕੇ ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ?",
        "or": "ଆପଣ କେଉଁ ଜିଲ୍ଲା କିମ୍ବା ଅଞ୍ଚଳରେ ରହୁଛନ୍ତି?",
    },
    "training_willingness": {
        "en": "Would you be willing to take a course or training if it helps you reach your work goal?",
        "hi": "अगर आपके काम के लक्ष्य में मदद मिले, तो क्या आप कोर्स या प्रशिक्षण लेना चाहेंगे?",
        "hinglish": "Agar aapke kaam ke goal mein madad mile, to kya aap course ya training karna chahenge?",
        "te": "మీ పని లక్ష్యానికి ఉపయోగపడితే కోర్సు లేదా శిక్షణ తీసుకోవడానికి సిద్ధంగా ఉన్నారా?",
        "ta": "உங்கள் வேலை இலக்கை அடைய உதவுமானால் ஒரு பாடநெறி அல்லது பயிற்சி எடுக்க தயாரா?",
        "kn": "ನಿಮ್ಮ ಕೆಲಸದ ಗುರಿ ತಲುಪಲು ಸಹಾಯವಾದರೆ ಕೋರ್ಸ್ ಅಥವಾ ತರಬೇತಿ ಪಡೆಯಲು ಸಿದ್ಧರಿದ್ದೀರಾ?",
        "ml": "നിങ്ങളുടെ ജോലി ലക്ഷ്യം കൈവരിക്കാൻ സഹായിക്കുന്നുവെങ്കിൽ ഒരു കോഴ്‌സ് അല്ലെങ്കിൽ പരിശീലനം എടുക്കാൻ തയ്യാറാണോ?",
        "mr": "तुमच्या कामाच्या उद्दिष्टासाठी मदत होत असेल तर कोर्स किंवा प्रशिक्षण घ्यायला तयार आहात का?",
        "bn": "আপনার কাজের লক্ষ্য পূরণে সাহায্য করলে আপনি কি কোর্স বা প্রশিক্ষণ নিতে রাজি?",
        "gu": "તમારા કામના લક્ષ્યમાં મદદ મળે તો તમે કોર્સ અથવા તાલીમ લેવા તૈયાર છો?",
        "pa": "ਜੇ ਇਹ ਤੁਹਾਡੇ ਕੰਮ ਦੇ ਲਕਸ਼ ਤੱਕ ਪਹੁੰਚਣ ਵਿੱਚ ਮਦਦ ਕਰੇ, ਤਾਂ ਕੀ ਤੁਸੀਂ ਕੋਰਸ ਜਾਂ ਟ੍ਰੇਨਿੰਗ ਲੈਣ ਲਈ ਤਿਆਰ ਹੋ?",
        "or": "ଆପଣଙ୍କ କାମର ଲକ୍ଷ୍ୟ ପୂରଣରେ ସାହାଯ୍ୟ କଲେ ଆପଣ କୋର୍ସ କିମ୍ବା ପ୍ରଶିକ୍ଷଣ ନେବାକୁ ପ୍ରସ୍ତୁତ କି?",
    },
}

PRIORITY = [
    "education",
    "livelihood_signal",
    "experience",
    "employment_preference",
    "location",
    "training_willingness",
]

def _language_family(language_code: Optional[str]) -> str:
    if not language_code:
        return "en"
    code = language_code.lower().replace("_", "-").split("-")[0]
    return code if code in SUPPORTED_LANGUAGES else "en"

EMPLOYMENT_CLARIFIERS = {
    "en": "Please choose one: job, self-employment, or your own business?",
    "hi": "सिर्फ एक विकल्प बताइए: नौकरी, स्वरोज़गार, या बिजनेस?",
    "hinglish": "Sirf ek option boliye: naukri/job, self-employment, ya apna business?",
    "te": "ఒకటి మాత్రమే చెప్పండి: ఉద్యోగం, స్వయం ఉపాధి, లేదా సొంత వ్యాపారం?",
    "ta": "ஒன்றை மட்டும் சொல்லுங்கள்: வேலை, சுயதொழில், அல்லது சொந்த வியாபாரம்?",
    "kn": "ಒಂದನ್ನು ಮಾತ್ರ ಹೇಳಿ: ಉದ್ಯೋಗ, ಸ್ವಯಂ ಉದ್ಯೋಗ, ಅಥವಾ ಸ್ವಂತ ವ್ಯವಹಾರ?",
    "ml": "ഒന്ന് മാത്രം പറയൂ: ജോലി, സ്വയംതൊഴിൽ, അല്ലെങ്കിൽ സ്വന്തം ബിസിനസ്?",
    "mr": "फक्त एक पर्याय सांगा: नोकरी, स्वयंरोजगार, की स्वतःचा व्यवसाय?",
    "bn": "একটি বেছে বলুন: চাকরি, স্বনিয়োজিত কাজ, নাকি নিজের ব্যবসা?",
    "gu": "એક વિકલ્પ કહો: નોકરી, સ્વરોજગાર કે પોતાનો વ્યવસાય?",
    "pa": "ਇੱਕ ਚੋਣ ਦੱਸੋ: ਨੌਕਰੀ, ਸਵੈ-ਰੋਜ਼ਗਾਰ ਜਾਂ ਆਪਣਾ ਕਾਰੋਬਾਰ?",
    "or": "ଗୋଟିଏ ବିକଳ୍ପ କୁହନ୍ତୁ: ଚାକିରି, ସ୍ୱୟଂରୋଜଗାର, କିମ୍ବା ନିଜ ବ୍ୟବସାୟ?",
}

def employment_clarifier(language_code: Optional[str] = None) -> str:
    lang = _language_family(language_code)
    return EMPLOYMENT_CLARIFIERS.get(lang, EMPLOYMENT_CLARIFIERS["en"])

class CounterQuestionEngine:
    def __init__(self, checker: Optional[ProfileCompletenessChecker] = None):
        self.checker = checker or ProfileCompletenessChecker()

    def next_missing_field(self, profile: BeneficiaryProfile) -> Optional[str]:
        report = self.checker.check(profile)
        missing = set(report.missing_critical + report.missing_enrichment)
        for field in PRIORITY:
            if field in missing:
                return field
        return None

    def next_question(self, profile: BeneficiaryProfile, language_code: Optional[str] = None) -> Optional[str]:
        field = self.next_missing_field(profile)
        if field is None:
            return None
        lang = _language_family(language_code or profile.language)
        return QUESTIONS[field].get(lang, QUESTIONS[field]["en"])
