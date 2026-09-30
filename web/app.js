/* ==========================================================================
   HADJ NO-TOUCH OFFLINE AI — landing PWA
   Trilingual runtime (ar / fr / en), gesture atlas, command atlas, install flow.
   ========================================================================== */
(() => {
  "use strict";

  const LANG_KEY = "hadj.lang";
  const SUPPORTED = ["ar", "fr", "en"];

  /* ------------------------------ content ------------------------------ */

  const GESTURES = [
    { id: "point", tone: "", pose: [0, 78, 92, 100, 62], rot: 0, rot2: 0, slide: 0 },
    { id: "pinch", tone: "", pose: [-26, 74, 90, 98, 57], rot: 0, rot2: 0, slide: 0 },
    { id: "pinch2", tone: "", pose: [-26, 74, 90, 98, 57], rot: 0, rot2: 0, slide: 0 },
    { id: "hold", tone: "", pose: [-26, 74, 90, 98, 57], rot: 0, rot2: -6, slide: 0 },
    { id: "palm", tone: "neutral", pose: [4, 0, 4, 10, -8], rot: 0, rot2: 0, slide: 0 },
    { id: "scroll", tone: "neutral", pose: [0, 0, 88, 96, 45], rot: 0, rot2: 0, slide: 0 },
    { id: "left", tone: "", pose: [-26, 74, 90, 98, 57], rot: 0, rot2: 0, slide: 22 },
    { id: "right", tone: "", pose: [-26, 74, 90, 98, 57], rot: 0, rot2: 0, slide: -22 },
    { id: "thumbup", tone: "confirm", pose: [80, 88, 94, 100, 47], rot: 0, rot2: -4, slide: 0 },
    { id: "fist", tone: "danger", pose: [84, 90, 95, 100, 137], rot: 0, rot2: 0, slide: 0 }
  ];

  const DIGITS = [
    { k: "index", x: 26, y: 38, x2: 26, y2: 15, o: "26px 38px" },
    { k: "middle", x: 32, y: 35, x2: 32, y2: 12, o: "32px 35px" },
    { k: "ring", x: 38, y: 37, x2: 38, y2: 16, o: "38px 37px" },
    { k: "pinky", x: 43, y: 41, x2: 43, y2: 24, o: "43px 41px" },
    { k: "thumb", x: 21, y: 46, x2: 10, y2: 36, o: "21px 46px" }
  ];

  const DICT = {
    fr: {
      "a11y.skip": "Aller au contenu",
      "nav.arch": "Architecture", "nav.gestures": "Gestes", "nav.voice": "Voix",
      "nav.security": "Sécurité", "nav.privacy": "Confidentialité", "nav.run": "Lancer",
      "nav.perf": "Performance", "nav.faq": "FAQ", "nav.install": "Installer", "nav.theme": "Changer le thème",
      "nav.aria": "Sections", "nav.langaria": "Langue", "nav.menu": "Ouvrir le menu",
      "hero.eyebrow": "Hors ligne par conception · IA 100% locale",
      "hero.title": "Contrôlez votre ordinateur sans le toucher.",
      "hero.lead": "Voix, gestes de la main et vision de l'écran fusionnés en une seule couche sensorielle. Aucune donnée ne quitte la machine, aucun appel cloud, aucune latence réseau.",
      "hero.cta1": "Lancer le projet", "hero.cta2": "Voir les gestes",
      "hero.m1": "Windows 10 / 11", "hero.m2": "points de la main", "hero.m3": "avec RTL natif",
      "hero.hudaria": "Aperçu du tableau de bord temps réel : squelette de la main, curseur virtuel et journal d'audit local",
      "hero.hudlive": "EN DIRECT", "hero.hlisten": "ÉCOUTE", "hero.htrack": "MAIN SUIVIE", "hero.hlocal": "local",
      "trust.1": "appel cloud", "trust.2": "langues actives", "trust.3": "repères 3D de la main", "trust.4": "sur la machine",
      "arch.eyebrow": "Architecture", "arch.title": "De l'intention à l'action, en neuf étages",
      "arch.lead": "Chaque commande traverse la même chaîne contrôlée. Le moteur de sécurité est le seul point de passage obligatoire vers le système.",
      "arch.n1": "Opérateur", "arch.d1": "Voix, geste ou regard.",
      "arch.n2": "Capteurs", "arch.d2": "Micro et caméra 640×480.",
      "arch.n3": "Moteur d'entrée", "arch.d3": "Squelette 21 points MediaPipe, Vosk / SAPI.",
      "arch.n4": "Intention", "arch.d4": "Règles multilingues, regex, LLM local.",
      "arch.n5": "Orchestrateur", "arch.d5": "Fusion multimodale, priorité, anti-rebond.",
      "arch.n6": "Sécurité", "arch.d6": "Portes LOW → CRITICAL.",
      "arch.n7": "Automatisation", "arch.d7": "PyAutoGUI, Win32, Pycaw, SBC.",
      "arch.n8": "Cibles", "arch.d8": "Applications, fichiers, navigateur, système.",
      "arch.n9": "Retour", "arch.d9": "HUD, curseur néon, synthèse locale.",
      "g.eyebrow": "Gestes", "g.title": "Dix gestes, une souris virtuelle",
      "g.lead": "Le suivi des 21 repères de la main est filtré par une moyenne exponentielle, puis interprété en gestes discrets. Survolez une carte pour voir la pose.",
      "g.point.n": "Index tendu", "g.point.a": "Index étendu, autres doigts repliés", "g.point.r": "Curseur",
      "g.pinch.n": "Pince", "g.pinch.a": "L'extrémité du pouce touche l'index", "g.pinch.r": "Clic gauche",
      "g.pinch2.n": "Double pince", "g.pinch2.a": "Deux pinces en moins de 0,4 s", "g.pinch2.r": "Double clic",
      "g.hold.n": "Pince maintenue", "g.hold.a": "Contact maintenu plus de 0,35 s", "g.hold.r": "Glisser-déposer",
      "g.palm.n": "Paume ouverte", "g.palm.a": "Les cinq doigts étendus", "g.palm.r": "Veille",
      "g.scroll.n": "Deux doigts", "g.scroll.a": "Index et majeur, la main bouge", "g.scroll.r": "Défilement",
      "g.left.n": "Balayage gauche", "g.left.a": "Mouvement horizontal rapide", "g.left.r": "Précédent",
      "g.right.n": "Balayage droit", "g.right.a": "Mouvement horizontal rapide", "g.right.r": "Suivant",
      "g.thumbup.n": "Pouce levé", "g.thumbup.a": "Pouce haut, autres doigts repliés", "g.thumbup.r": "Confirmer",
      "g.fist.n": "Poing fermé", "g.fist.a": "Tous les doigts repliés", "g.fist.r": "Annuler / arrêt",
      "v.eyebrow": "Commandes vocales", "v.title": "Trois langues, un seul vocabulaire",
      "v.lead": "Les mêmes intentions sont comprises en arabe, en français et en anglais, avec une saisie Unicode-safe : l'arabe se tape correctement dans n'importe quelle application.",
      "v.wake": "Mots d'activation", "v.tabsaria": "Langue des exemples", "v.stop": "Arrêt d'urgence",
      "v.stopphrase": "« Stop Hadj » · « توقف يا حاج » · « قف » · « Arrête » — ou poing fermé maintenu 2 s",
      "s.eyebrow": "Moteur de risque", "s.title": "Quatre niveaux, aucune exception",
      "s.lead": "Chaque intention est classée avant d'atteindre le système. Le niveau détermine si la commande part seule ou exige une confirmation.",
      "s.auto": "automatique", "s.opt": "configurable", "s.must": "obligatoire", "s.dual": "double",
      "s.d1": "Exécuté immédiatement, sans question.", "s.d2": "Confirmation selon les réglages.", "s.d3": "Confirmation obligatoire avant exécution.", "s.d4": "Double confirmation obligatoire.",
      "s.x1a": "Volume, luminosité", "s.x1b": "Lancer une application", "s.x1c": "Changer d'onglet",
      "s.x2a": "Fermer une fenêtre", "s.x2b": "Supprimer un fichier",
      "s.x3a": "Supprimer un dossier", "s.x3b": "Redémarrer, éteindre", "s.x3c": "Vider la corbeille",
      "s.x4a": "Formater un disque", "s.x4b": "Opérations de volume",
      "s.hf": "Confirmation mains libres — délai de 10 secondes",
      "s.cancel": "Annuler · poing fermé",
      "p.eyebrow": "Profils", "p.title": "Quatre régimes, un seul arbitrage",
      "p.lead": "Le nombre d'images par seconde pilote la consommation CPU. Choisissez selon la machine et le contexte d'usage.",
      "p.d1": "Charge CPU minimale, matériel ancien.", "p.d2": "Le compromis par défaut.",
      "p.d3": "Curseur parfaitement fluide.", "p.d4": "Vision d'écran et analyse d'intention locale.",
      "pr.eyebrow": "Confidentialité", "pr.title": "Rien ne sort de la machine",
      "pr.lead": "Ce n'est pas une promesse commerciale, c'est une contrainte d'architecture : le réseau externe est bloqué par défaut.",
      "pr.a": "Capture volatile", "pr.da": "Les images caméra et les flux audio vivent en mémoire vive puis sont immédiatement détruits. Aucune vidéo n'est enregistrée.",
      "pr.b": "Journal local seul", "pr.db": "Seules des métadonnées texte sont conservées dans un fichier JSONL, pour votre propre audit.",
      "pr.c": "Réseau coupé", "pr.dc": "Télémétrie désactivée, appels externes bloqués, transcription assurée par un moteur local.",
      "r.eyebrow": "Mise en route", "r.title": "Trois étapes", "r.lead": "Aucune installation réseau, aucun compte, aucune clé d'API.",
      "r.launch_btn": "Lancer / Vérifier l'application", "r.install_pwa": "Installer l'App Web (PWA)",
      "r.sac_title": "💡 Information Windows Smart App Control",
      "r.sac_desc": "Pour des raisons de sécurité, Windows 11 bloque les fichiers .bat téléchargés depuis le Web. <b>Aucun téléchargement n'est nécessaire</b> : double-cliquez directement sur <code>launch.bat</code> dans votre dossier local ou exécutez <code>python main.py</code>.",
      "r.s1": "Ouvrir le dossier", "r.d1": "Décompressez l'archive et ouvrez le répertoire du projet.",
      "r.s2": "Lancer", "r.d2": "Double-cliquez sur le lanceur, ou appelez Python directement.",
      "r.s3": "Calibrer et réveiller", "r.d3": "Lancez l'assistant de calibration, puis prononcez un mot d'activation.",
      "r.copy": "Copier la commande",
      "r.sp1": "Windows 10 / 11", "r.sp2": "Python 3.12", "r.sp3": "Webcam", "r.sp4": "Microphone", "r.sp5": "API compagnon 127.0.0.1:8766",
      "f.eyebrow": "FAQ", "f.title": "Questions fréquentes",
      "f.q1": "Est-ce que ça fonctionne sans internet ?", "f.a1": "Oui. La reconnaissance vocale, la reconnaissance des gestes et l'analyse d'intention tournent localement. Le réseau externe est bloqué par défaut.",
      "f.q2": "Quelles langues sont prises en charge ?", "f.a2": "L'arabe, le français et l'anglais, y compris l'affichage de droite à gauche pour l'arabe.",
      "f.q3": "Peut-on se passer de souris et de clavier ?", "f.a3": "Oui. L'index tendu déplace le curseur, une pince clique, une pince maintenue glisse. Un clavier virtuel sans aucune touche prend le relais pour la dictée.",
      "f.q4": "Que se passe-t-il si une commande est dangereuse ?", "f.a4": "Elle est classée par niveau de risque. Les niveaux HIGH et CRITICAL exigent une confirmation, donnée à la voix ou par le pouce levé. Le poing fermé annule à tout moment.",
      "f.q5": "Sur quelles machines ?", "f.a5": "Windows 10 et 11 avec Python 3.12, une webcam et un microphone. Le profil ECO permet de rester léger sur du matériel ancien.",
      "f.q6": "Peut-on l'utiliser pour l'accessibilité ?", "f.a6": "Oui. Le HUD à contraste élevé, le grand curseur, le clic à dwell et le mode multimodal sont prévus pour les situations où la précision pose problème.",
      "foot.lic": "licence ouverte", "foot.off": "0 requête réseau vers des tiers", "foot.top": "Revenir en haut",
      "im.t": "Installer & Lancer HADJ", "im.body": "Démarrez le contrôle sans toucher directement sur votre PC ou installez l'application Web PWA.",
      "im.launch_btn": "Lancer HADJ sur le PC",
      "im.sac_note": "💡 Sur Windows 11, exécutez directement launch.bat dans votre dossier local pour éviter tout blocage Smart App Control.",
      "im.go": "Installer l'application Web (PWA)", "im.no": "Fermer"
    },

    en: {
      "a11y.skip": "Skip to content",
      "nav.arch": "Architecture", "nav.gestures": "Gestures", "nav.voice": "Voice",
      "nav.security": "Security", "nav.privacy": "Privacy", "nav.run": "Run",
      "nav.perf": "Performance", "nav.faq": "FAQ", "nav.install": "Install",
      "nav.aria": "Sections", "nav.langaria": "Language", "nav.menu": "Open menu",
      "hero.eyebrow": "Offline by design · 100% local AI",
      "hero.title": "Control your computer without touching it.",
      "hero.lead": "Voice, hand gestures and screen vision fused into a single sensory layer. No data leaves the machine, no cloud call, no network latency.",
      "hero.cta1": "Run the project", "hero.cta2": "See the gestures",
      "hero.m1": "Windows 10 / 11", "hero.m2": "hand landmarks", "hero.m3": "native RTL",
      "hero.hudaria": "Live HUD preview: hand skeleton, virtual cursor and local audit log",
      "hero.hudlive": "LIVE", "hero.hlisten": "LISTENING", "hero.htrack": "HAND TRACKED", "hero.hlocal": "local",
      "trust.1": "cloud calls", "trust.2": "active languages", "trust.3": "3D hand landmarks", "trust.4": "on the machine",
      "arch.eyebrow": "Architecture", "arch.title": "From intent to action, in nine stages",
      "arch.lead": "Every command crosses the same controlled chain. The security engine is the single mandatory gate towards the system.",
      "arch.n1": "Operator", "arch.d1": "Voice, gesture or gaze.",
      "arch.n2": "Sensors", "arch.d2": "Microphone and 640×480 camera.",
      "arch.n3": "Input engine", "arch.d3": "21-landmark MediaPipe skeleton, Vosk / SAPI.",
      "arch.n4": "Intent", "arch.d4": "Multilingual rules, regex, local LLM.",
      "arch.n5": "Orchestrator", "arch.d5": "Multimodal fusion, priority, debounce.",
      "arch.n6": "Security", "arch.d6": "LOW → CRITICAL gates.",
      "arch.n7": "Automation", "arch.d7": "PyAutoGUI, Win32, Pycaw, SBC.",
      "arch.n8": "Targets", "arch.d8": "Apps, files, browser, system.",
      "arch.n9": "Feedback", "arch.d9": "HUD, neon cursor, local speech.",
      "g.eyebrow": "Gestures", "g.title": "Ten gestures, one virtual mouse",
      "g.lead": "The 21 hand landmarks are filtered with an exponential moving average, then resolved into discrete gestures. Hover a card to see the pose.",
      "g.point.n": "Index point", "g.point.a": "Index extended, others curled", "g.point.r": "Cursor",
      "g.pinch.n": "Pinch", "g.pinch.a": "Thumb tip meets index tip", "g.pinch.r": "Left click",
      "g.pinch2.n": "Double pinch", "g.pinch2.a": "Two pinches within 0.4 s", "g.pinch2.r": "Double click",
      "g.hold.n": "Pinch and hold", "g.hold.a": "Contact held over 0.35 s", "g.hold.r": "Drag and drop",
      "g.palm.n": "Open palm", "g.palm.a": "All five fingers extended", "g.palm.r": "Standby",
      "g.scroll.n": "Two fingers", "g.scroll.a": "Index and middle, hand moves", "g.scroll.r": "Scroll",
      "g.left.n": "Swipe left", "g.left.a": "Fast horizontal sweep left", "g.left.r": "Previous",
      "g.right.n": "Swipe right", "g.right.a": "Fast horizontal sweep right", "g.right.r": "Next",
      "g.thumbup.n": "Thumb up", "g.thumbup.a": "Thumb up, others curled", "g.thumbup.r": "Confirm",
      "g.fist.n": "Closed fist", "g.fist.a": "All fingers tightly curled", "g.fist.r": "Cancel / stop",
      "v.eyebrow": "Voice commands", "v.title": "Three languages, one vocabulary",
      "v.lead": "The same intents are understood in Arabic, French and English, with Unicode-safe typing: Arabic is typed correctly into any application.",
      "v.wake": "Wake words", "v.tabsaria": "Example language", "v.stop": "Emergency stop",
      "v.stopphrase": "“Stop Hadj” · “توقف يا حاج” · “قف” · “Arrête” — or a closed fist held for 2 s",
      "s.eyebrow": "Risk engine", "s.title": "Four tiers, no exceptions",
      "s.lead": "Every intent is classified before it reaches the system. The tier decides whether the command runs alone or requires confirmation.",
      "s.auto": "automatic", "s.opt": "configurable", "s.must": "mandatory", "s.dual": "dual",
      "s.d1": "Executed immediately, no question.", "s.d2": "Confirmation depends on your settings.", "s.d3": "Confirmation required before execution.", "s.d4": "Dual confirmation required.",
      "s.x1a": "Volume, brightness", "s.x1b": "Launch an application", "s.x1c": "Switch tab",
      "s.x2a": "Close a window", "s.x2b": "Delete a file",
      "s.x3a": "Delete a directory", "s.x3b": "Restart, shut down", "s.x3c": "Empty the recycle bin",
      "s.x4a": "Format a drive", "s.x4b": "Volume operations",
      "s.hf": "Hands-free confirmation — 10 second timeout",
      "s.cancel": "Cancel · closed fist",
      "p.eyebrow": "Profiles", "p.title": "Four regimes, one trade-off",
      "p.lead": "Frames per second drives CPU usage. Pick according to the machine and the context.",
      "p.d1": "Minimal CPU load, older hardware.", "p.d2": "The default compromise.",
      "p.d3": "Perfectly fluid cursor.", "p.d4": "Screen vision and local intent analysis.",
      "pr.eyebrow": "Privacy", "pr.title": "Nothing leaves the machine",
      "pr.lead": "This is not a marketing promise, it is an architectural constraint: outbound network access is blocked by default.",
      "pr.a": "Volatile capture", "pr.da": "Camera frames and audio streams live in volatile memory and are destroyed immediately. No video is ever recorded.",
      "pr.b": "Local log only", "pr.db": "Only text metadata is kept, in a JSONL file, for your own audit.",
      "pr.c": "Network cut", "pr.dc": "Telemetry disabled, outbound calls blocked, transcription handled by a local engine.",
      "r.eyebrow": "Get started", "r.title": "Three steps", "r.lead": "No network install, no account, no API key.",
      "r.s1": "Open the folder", "r.d1": "Unpack the archive and open the project directory.",
      "r.s2": "Launch", "r.d2": "Double-click the launcher, or call Python directly.",
      "r.s3": "Calibrate and wake", "r.d3": "Run the calibration wizard, then say a wake word.",
      "r.copy": "Copy command",
      "r.sp1": "Windows 10 / 11", "r.sp2": "Python 3.12", "r.sp3": "Webcam", "r.sp4": "Microphone", "r.sp5": "Companion API 127.0.0.1:8766",
      "f.eyebrow": "FAQ", "f.title": "Frequently asked",
      "f.q1": "Does it work without internet?", "f.a1": "Yes. Speech recognition, gesture recognition and intent analysis all run locally. Outbound network is blocked by default.",
      "f.q2": "Which languages are supported?", "f.a2": "Arabic, French and English, including right-to-left rendering for Arabic.",
      "f.q3": "Can I do without a mouse and keyboard?", "f.a3": "Yes. An extended index moves the cursor, a pinch clicks, a held pinch drags. A fully touchless on-screen keyboard covers dictation.",
      "f.q4": "What happens if a command is dangerous?", "f.a4": "It is graded by risk tier. HIGH and CRITICAL require confirmation, given by voice or by a thumbs up. A closed fist cancels at any time.",
      "f.q5": "Which machines?", "f.a5": "Windows 10 and 11 with Python 3.12, a webcam and a microphone. The ECO profile stays light on older hardware.",
      "f.q6": "Can I use it for accessibility?", "f.a6": "Yes. The high-contrast HUD, large cursor, dwell click and multimodal mode exist precisely for situations where precision is a problem.",
      "foot.lic": "open licence", "foot.off": "0 third-party network requests", "foot.top": "Back to top",
      "im.t": "Install HADJ", "im.body": "Add this page to your home screen for a full-screen launch and offline use.",
      "im.go": "Install now", "im.no": "Later"
    },

    ar: {
      "a11y.skip": "تخطَّ إلى المحتوى",
      "nav.arch": "البنية", "nav.gestures": "الإيماءات", "nav.voice": "الصوت",
      "nav.security": "الأمان", "nav.privacy": "الخصوصية", "nav.run": "التشغيل",
      "nav.perf": "الأداء", "nav.faq": "أسئلة", "nav.install": "تثبيت",
      "nav.aria": "الأقسام", "nav.langaria": "اللغة", "nav.menu": "فتح القائمة",
      "hero.eyebrow": "يعمل دون إنترنت · ذكاء اصطناعي محلي بالكامل",
      "hero.title": "تحكّم في حاسوبك دون أن تلمسه.",
      "hero.lead": "صوت وإيماءات اليد ورؤية الشاشة في طبقة حسّية واحدة. لا تغادر أي بيانات جهازك، ولا يوجد أي اتصال سحابي، ولا أي تأخير شبكي.",
      "hero.cta1": "شغّل المشروع", "hero.cta2": "استعرض الإيماءات",
      "hero.m1": "ويندوز 10 / 11", "hero.m2": "نقطة يد", "hero.m3": "مع دعم الكتابة من اليمين",
      "hero.hudaria": "معاينة مباشرة للوحة التحكّم: هيكل اليد والمؤشر الافتراضي وسجل التدقيق المحلي",
      "hero.hudlive": "مباشر", "hero.hlisten": "يستمع", "hero.htrack": "تتبّع اليد", "hero.hlocal": "محلي",
      "trust.1": "اتصال سحابي", "trust.2": "لغات مفعّلة", "trust.3": "نقطة ثلاثية الأبعاد لليد", "trust.4": "على جهازك",
      "arch.eyebrow": "البنية", "arch.title": "من النيّة إلى الفعل، عبر تسع مراحل",
      "arch.lead": "كل أمر يمرّ بسلسلة واحدة محكومة. محرّك الأمان هو البوابة الوحيدة الإلزامية نحو النظام.",
      "arch.n1": "المستخدم", "arch.d1": "بالصوت أو الإيماءة أو النظر.",
      "arch.n2": "المستشعرات", "arch.d2": "ميكروفون وكاميرا بدقة 640×480.",
      "arch.n3": "محرّك الإدخال", "arch.d3": "هيكل يد من 21 نقطة عبر MediaPipe، مع Vosk أو SAPI.",
      "arch.n4": "النيّة", "arch.d4": "قواعد متعددة اللغات وتعبيرات نمطية ونموذج محلي.",
      "arch.n5": "المنسّق", "arch.d5": "دمج متعدّد الوسائط وترتيب الأولويات وكبت التكرار.",
      "arch.n6": "الأمان", "arch.d6": "بوابات من LOW إلى CRITICAL.",
      "arch.n7": "الأتمتة", "arch.d7": "PyAutoGUI وWin32 وPycaw وSBC.",
      "arch.n8": "الأهداف", "arch.d8": "التطبيقات والملفات والمتصفح والنظام.",
      "arch.n9": "الاستجابة", "arch.d9": "لوحة علوية ومؤشر مضيء ونطق محلي.",
      "g.eyebrow": "الإيماءات", "g.title": "عشر إيماءات تُغني عن الفأرة",
      "g.lead": "تُنعَّم النقاط الإحدى والعشرون لليد بمتوسط متحرك أُسّي، ثم تُترجَم إلى إيماءات منفصلة. مرّر المؤشر فوق أي بطاقة لرؤية الوضعية.",
      "g.point.n": "توجيه بالسبابة", "g.point.a": "السبابة ممدودة وباقي الأصابع مطوية", "g.point.r": "تحريك المؤشر",
      "g.pinch.n": "إيماءة القرص", "g.pinch.a": "طرف الإبهام يلامس طرف السبابة", "g.pinch.r": "نقرة يسارية",
      "g.pinch2.n": "نقرتان", "g.pinch2.a": "ضغطتان خلال 0,4 ثانية", "g.pinch2.r": "نقرة مزدوجة",
      "g.hold.n": "ضغط مستمر", "g.hold.a": "بقاء التماس أكثر من 0,35 ثانية", "g.hold.r": "سحب وإفلات",
      "g.palm.n": "راحة مفتوحة", "g.palm.a": "الأصابع الخمسة ممدودة", "g.palm.r": "وضع الانتظار",
      "g.scroll.n": "إصبعان", "g.scroll.a": "السبابة والوسطى مع تحريك اليد", "g.scroll.r": "تمرير",
      "g.left.n": "سحبة يسار", "g.left.a": "حركة أفقية سريعة نحو اليسار", "g.left.r": "السابق",
      "g.right.n": "سحبة يمين", "g.right.a": "حركة أفقية سريعة نحو اليمين", "g.right.r": "التالي",
      "g.thumbup.n": "إبهام لأعلى", "g.thumbup.a": "الإبهام مرفوع وباقي الأصابع مطوية", "g.thumbup.r": "تأكيد",
      "g.fist.n": "قبضة", "g.fist.a": "جميع الأصابع مطوية بإحكام", "g.fist.r": "إلغاء / إيقاف",
      "v.eyebrow": "الأوامر الصوتية", "v.title": "ثلاث لغات ومفردات واحدة",
      "v.lead": "تُفهم النيّات نفسها بالعربية والفرنسية والإنجليزية، مع كتابة آمنة بترميز يونيكود: تُكتب العربية بشكل صحيح داخل أي تطبيق.",
      "v.wake": "كلمات التنبيه", "v.tabsaria": "لغة الأمثلة", "v.stop": "الإيقاف الطارئ",
      "v.stopphrase": "«توقف يا حاج» · «قف» · «Stop Hadj» · «Arrête» — أو إمساك القبضة ثانيتين",
      "s.eyebrow": "محرّك المخاطر", "s.title": "أربعة مستويات، بلا استثناء",
      "s.lead": "تُصنَّف كل نيّة قبل وصولها إلى النظام. ويحدّد المستوى هل يُنفَّذ الأمر وحده أم يحتاج إلى تأكيد.",
      "s.auto": "تلقائي", "s.opt": "قابل للتهيئة", "s.must": "إلزامي", "s.dual": "مزدوج",
      "s.d1": "يُنفَّذ فورًا دون سؤال.", "s.d2": "التأكيد حسب إعداداتك.", "s.d3": "تأكيد إلزامي قبل التنفيذ.", "s.d4": "تأكيد مزدوج إلزامي.",
      "s.x1a": "الصوت والسطوع", "s.x1b": "تشغيل تطبيق", "s.x1c": "تبديل التبويب",
      "s.x2a": "إغلاق نافذة", "s.x2b": "حذف ملف",
      "s.x3a": "حذف مجلد", "s.x3b": "إعادة التشغيل والإطفاء", "s.x3c": "إفراغ سلة المحذوفات",
      "s.x4a": "تهيئة قرص", "s.x4b": "عمليات على الأقراص",
      "s.hf": "تأكيد دون لمس — مهلة عشر ثوانٍ",
      "s.cancel": "إلغاء · القبضة",
      "p.eyebrow": "الأوضاع", "p.title": "أربعة أوضاع، ومقايضة واحدة",
      "p.lead": "عدد الإطارات في الثانية يحدّد استهلاك المعالج. اختر بحسب الجهاز وسياق الاستخدام.",
      "p.d1": "أقل استهلاك للمعالج، وأجهزة قديمة.", "p.d2": "الوضع الافتراضي المتوازن.",
      "p.d3": "مؤشر شديد الانسيابية.", "p.d4": "رؤية الشاشة وتحليل النيّة محليًا.",
      "pr.eyebrow": "الخصوصية", "pr.title": "لا شيء يغادر الجهاز",
      "pr.lead": "هذا ليس وعدًا تسويقيًا بل قيد معماري: الشبكة الخارجية محجوبة افتراضيًا.",
      "pr.a": "التقاط عابر", "pr.da": "تعيش إطارات الكاميرا ومسارات الصوت في الذاكرة المؤقتة ثم تُتلف فورًا. لا يُسجَّل أي فيديو.",
      "pr.b": "سجلّ محلي فقط", "pr.db": "لا يُحفظ سوى بيانات نصية في ملف JSONL، لغرض تدقيقك أنت.",
      "pr.c": "الشبكة مقطوعة", "pr.dc": "التتبّع معطّل، والاتصالات الخارجية محجوبة، والتفريغ يتم عبر محرّك محلي.",
      "r.eyebrow": "البدء", "r.title": "ثلاث خطوات", "r.lead": "لا تنصيب عبر الشبكة، ولا حساب، ولا مفتاح واجهة.",
      "r.s1": "افتح المجلد", "r.d1": "فكّ الضغط عن الأرشيف وافتح مجلد المشروع.",
      "r.s2": "شغّل", "r.d2": "انقر نقرًا مزدوجًا على ملف التشغيل، أو استدعِ بايثون مباشرة.",
      "r.s3": "اضبط واستدعِ", "r.d3": "شغّل معالج المعايرة، ثم انطق بكلمة تنبيه.",
      "r.copy": "نسخ الأمر",
      "r.sp1": "ويندوز 10 / 11", "r.sp2": "بايثون 3.12", "r.sp3": "كاميرا", "r.sp4": "ميكروفون", "r.sp5": "واجهة مرافقة 127.0.0.1:8766",
      "f.eyebrow": "أسئلة", "f.title": "أسئلة متكررة",
      "f.q1": "هل يعمل دون إنترنت؟", "f.a1": "نعم. التعرّف على الصوت وعلى الإيماءات وتحليل النيّة تعمل جميعها محليًا، والشبكة الخارجية محجوبة افتراضيًا.",
      "f.q2": "ما اللغات المدعومة؟", "f.a2": "العربية والفرنسية والإنجليزية، مع عرض من اليمين إلى اليسار للعربية.",
      "f.q3": "هل يمكن الاستغناء عن الفأرة ولوحة المفاتيح؟", "f.a3": "نعم. مدّ السبابة يحرّك المؤشر، والضغط يقرّر، والضغط المستمر يسحب. ولوحة مفاتيح افتراضية بلا أزرار تتولّى الإملاء.",
      "f.q4": "ماذا يحدث إذا كان الأمر خطيرًا؟", "f.a4": "يُصنَّف حسب مستوى الخطر. يحتاج المستوى HIGH وCRITICAL إلى تأكيد يُقال صوتيًا أو بالإبهام لأعلى. والقبضة تلغي في أي لحظة.",
      "f.q5": "ما الأجهزة المدعومة؟", "f.a5": "ويندوز 10 و11 مع بايثون 3.12 وكاميرا وميكروفون. ووضع ECO يخفّض الاستهلاك على الأجهزة القديمة.",
      "f.q6": "هل يصلح لإتاحة الوصول؟", "f.a6": "نعم. اللوحة العلوية عالية التباين، والمؤشر الكبير، والنقر بالثبات، والوضع متعدّد الوسائط موجودة أصلًا للمواقف التي يصعب فيها الدقة.",
      "foot.lic": "رخصة مفتوحة", "foot.off": "صفر طلب شبكة نحو أطراف خارجية", "foot.top": "العودة إلى الأعلى",
      "im.t": "تثبيت HADJ", "im.body": "أضِف هذه الصفحة إلى شاشتك الرئيسية لتشغيل بملء الشاشة ويعمل دون إنترنت.",
      "im.go": "ثبّت الآن", "im.no": "لاحقًا"
    }
  };

  const VOICE = {
    fr: [
      { t: "Applications", c: ["Ouvre Chrome", "Lance Word", "Ferme la fenêtre", "Ouvre YouTube"] },
      { t: "Fichiers et navigation", c: ["Ouvre les téléchargements", "Mes documents", "Surface de bureau", "Nouveau dossier"] },
      { t: "Dictée", c: ["Écris bonjour à tous", "Supprime le dernier mot", "Sélectionne tout", "Colle"] },
      { t: "Système et médias", c: ["Augmente le volume", "Capture l'écran", "Fais défiler vers le bas", "Met en pause"] }
    ],
    en: [
      { t: "Applications", c: ["Open Chrome", "Launch VS Code", "Close window", "Open YouTube"] },
      { t: "Files and navigation", c: ["Open downloads", "My documents", "Desktop", "New folder"] },
      { t: "Dictation", c: ["Type hello everyone", "Delete last word", "Select all", "Paste"] },
      { t: "System and media", c: ["Volume up", "Take a screenshot", "Scroll down", "Pause"] }
    ],
    ar: [
      { t: "التطبيقات", c: ["افتح كروم", "شغّل وورد", "أغلق النافذة", "افتح يوتيوب"] },
      { t: "الملفات والتنقّل", c: ["افتح التنزيلات", "مستنداتي", "سطح المكتب", "أنشئ مجلداً جديداً"] },
      { t: "الإملاء", c: ["اكتب مرحبا بكم", "احذف آخر كلمة", "حدد الكل", "الصق"] },
      { t: "النظام والوسائط", c: ["ارفع الصوت", "التقط صورة للشاشة", "مرّر لأسفل", "إيقاف مؤقت"] }
    ]
  };

  const INSTALL_STEPS = {
    ios: {
      body: { fr: "Sur iPhone et iPad, l'installation passe par Safari.", en: "On iPhone and iPad, installation goes through Safari.", ar: "على آيفون وآيباد يتم التثبيت عبر سفاري." },
      steps: {
        fr: ["Touchez le bouton Partager en bas de l'écran.", "Choisissez « Sur l'écran d'accueil ».", "Confirmez avec Ajouter."],
        en: ["Tap the Share button at the bottom of the screen.", "Choose “Add to Home Screen”.", "Confirm with Add."],
        ar: ["اضغط زر المشاركة أسفل الشاشة.", "اختر «إلى الشاشة الرئيسية».", "أكّد بإضافة."]
      }
    },
    desktop: {
      body: { fr: "Votre navigateur ne propose pas d'installation automatique.", en: "Your browser does not offer automatic installation.", ar: "متصفحك لا يوفّر تثبيتًا تلقائيًا." },
      steps: {
        fr: ["Ouvrez le menu du navigateur (⋮ ou •••).", "Choisissez « Installer l'application » ou « Ajouter à l'écran d'accueil ».", "Confirmez l'installation."],
        en: ["Open the browser menu (⋮ or •••).", "Choose “Install app” or “Add to home screen”.", "Confirm the installation."],
        ar: ["افتح قائمة المتصفح (⋮ أو •••).", "اختر «تثبيت التطبيق» أو «إضافة إلى الشاشة الرئيسية».", "أكّد التثبيت."]
      }
    }
  };

  const LOG_SEED = [
    '{"ts":"14:02:11","intent":"open_app","risk":"LOW","cmd":"chrome","ok":true}',
    '{"ts":"14:02:14","intent":"volume.up","risk":"LOW","cmd":"+5%","ok":true}',
    '{"ts":"14:02:19","intent":"point.target","risk":"LOW","cmd":"btn_send","ok":true}',
    '{"ts":"14:02:26","intent":"scroll.down","risk":"LOW","cmd":"dx:0 dy:340","ok":true}',
    '{"ts":"14:02:31","intent":"dictation","risk":"LOW","cmd":"مرحبا","ok":true}',
    '{"ts":"14:02:38","intent":"window.snap.right","risk":"LOW","cmd":"snap","ok":true}',
    '{"ts":"14:02:44","intent":"shell.delete.dir","risk":"HIGH","cmd":"D:/cache","ok":false}'
  ];

  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ------------------------------- i18n -------------------------------- */

  let lang = "fr";
  let voiceTab = null;
  let voiceTabPinned = false;
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  function pick(l) { return SUPPORTED.includes(l) ? l : "fr"; }

  function setLang(l, persist) {
    lang = pick(l);
    const dict = DICT[lang];
    const rtl = lang === "ar";

    document.documentElement.lang = lang;
    document.documentElement.dir = rtl ? "rtl" : "ltr";

    $$("[data-i18n]").forEach((el) => {
      const v = dict[el.dataset.i18n];
      if (v) el.textContent = v;
    });
    $$("[data-i18n-attr]").forEach((el) => {
      el.dataset.i18nAttr.split("|").forEach((pair) => {
        const [attr, key] = pair.split(":");
        const v = dict[key.trim()];
        if (v) el.setAttribute(attr.trim(), v);
      });
    });

    $$(".lang button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
    $$("[data-stopphrase]").forEach((el) => {
      el.textContent = dict["v.stopphrase"];
      el.setAttribute("dir", rtl ? "rtl" : "ltr");
    });
    const status = $("#lang-status");
    if (status) status.textContent = dict["nav.langaria"] + " : " + dict["im.t"].split(" ")[1];
    if (!voiceTabPinned) voiceTab = lang;
    selectTab(voiceTab, false);
    renderVoice();
    buildGestures();

    if (persist) { try { localStorage.setItem(LANG_KEY, lang); } catch (_) { /* private mode */ } }
  }

  /* ------------------------------ gestures ----------------------------- */

  function handSVG(g) {
    const digits = DIGITS.map((d, i) =>
      `<line class="d d-${d.k}" style="transform-origin:${d.o};--r:${g.pose[i]}" x1="${d.x}" y1="${d.y}" x2="${d.x2}" y2="${d.y2}"/>`
    ).join("");
    return `<svg class="ghand" style="--rot:${g.rot}deg;--rot2:${g.rot2}deg;--slide:${g.slide}px" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <path class="palm" d="M20 40 q0 -8 8 -8 h10 q10 0 10 9 v6 q0 11 -14 11 t-14 -11 z"/>
      <g>${digits}</g>
    </svg>`;
  }

  function buildGestures() {
    const host = $("[data-gestures]");
    if (!host) return;
    const dict = DICT[lang];
    host.innerHTML = GESTURES.map((g) => {
      const n = dict[`g.${g.id}.n`] || g.id;
      const a = dict[`g.${g.id}.a`] || "";
      const r = dict[`g.${g.id}.r`] || "";
      return `<li class="gcard${g.tone ? " gcard--" + g.tone : ""}">
        ${handSVG(g)}
        <h3 lang="${lang}" dir="${lang === "ar" ? "rtl" : "ltr"}">${n}</h3>
        <p lang="${lang}" dir="${lang === "ar" ? "rtl" : "ltr"}">${a}</p>
        <span class="gchip">${r}</span>
      </li>`;
    }).join("");
  }

  /* -------------------------------- voice ------------------------------- */

  function renderVoice() {
    const host = $("[data-voice]");
    if (!host) return;
    const t = voiceTab || lang;
    const rtl = t === "ar";
    host.innerHTML = `<div class="vgrid" dir="${rtl ? "rtl" : "ltr"}" lang="${t}">` + VOICE[t].map((g) => `
      <article class="vgroup">
        <h4>${g.t}</h4>
        <ul>${g.c.map((c) => `<li>${c}</li>`).join("")}</ul>
      </article>`).join("") + `</div>`;
  }

  function selectTab(id, focus) {
    const bar = $("[data-tabs]");
    if (!bar) return;
    voiceTab = pick(id);
    const tabs = $$("[data-tab]", bar);
    tabs.forEach((b) => {
      const on = b.dataset.tab === voiceTab;
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
      if (on && focus) b.focus();
    });
    const panel = $("[data-voice]");
    const active = tabs.find((b) => b.dataset.tab === id);
    if (panel && active) panel.setAttribute("aria-labelledby", active.id);
  }

  function bindTabs() {
    const bar = $("[data-tabs]");
    if (!bar) return;
    const tabs = $$("[data-tab]", bar);
    tabs.forEach((b) => b.addEventListener("click", () => { voiceTabPinned = true; selectTab(b.dataset.tab, false); renderVoice(); }));
    bar.addEventListener("keydown", (e) => {
      const i = tabs.indexOf(document.activeElement);
      if (i < 0) return;
      const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!step && e.key !== "Home" && e.key !== "End") return;
      e.preventDefault();
      const n = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (i + step + tabs.length) % tabs.length;
      selectTab(tabs[n].dataset.tab, true);
      voiceTabPinned = true;
      renderVoice();
    });
  }

  /* ----------------------------- chrome bits ---------------------------- */

  function bindNav() {
    const nav = $("#nav");
    const bar = $(".nav__progress i");
    const onScroll = () => {
      const y = scrollY;
      nav.classList.toggle("is-stuck", y > 12);
      const max = document.documentElement.scrollHeight - innerHeight;
      if (bar) bar.style.width = (max > 0 ? (y / max) * 100 : 0) + "%";
      const top = $("[data-top]");
      if (top) top.hidden = y < 600;
    };
    addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    const links = $$(".nav__links a");
    const sections = links.map((a) => $(a.getAttribute("href"))).filter(Boolean);
    if (sections.length && "IntersectionObserver" in window) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((en) => {
          if (!en.isIntersecting) return;
          links.forEach((a) => a.classList.toggle("is-on", a.getAttribute("href") === "#" + en.target.id));
        });
      }, { rootMargin: "-45% 0px -50% 0px" });
      sections.forEach((s) => io.observe(s));
    }

    const burger = $(".burger");
    const sheet = $("#mobile-menu");
    const setMenu = (open) => {
      burger.setAttribute("aria-expanded", String(open));
      sheet.hidden = !open;
      document.body.style.overflow = open ? "hidden" : "";
    };
    burger.addEventListener("click", () => setMenu(burger.getAttribute("aria-expanded") !== "true"));
    $$("#mobile-menu a").forEach((a) => a.addEventListener("click", () => setMenu(false)));
    addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });
  }

  function bindCopy() {
    $$(".code").forEach((box) => {
      $(".code__b", box).addEventListener("click", async () => {
        const text = box.dataset.copy;
        try {
          await navigator.clipboard.writeText(text);
        } catch (_) {
          const ta = document.createElement("textarea");
          ta.value = text; document.body.append(ta); ta.select();
          try { document.execCommand("copy"); } catch (__) { /* clipboard unavailable */ }
          ta.remove();
        }
        box.classList.add("is-done");
      });
    });
  }

  function runLog() {
    const host = $("[data-log]");
    if (!host || reduceMotion) return;
    let i = host.children.length;
    const push = () => {
      const li = document.createElement("li");
      li.textContent = LOG_SEED[i % LOG_SEED.length];
      li.classList.add("is-new");
      host.append(li);
      while (host.children.length > 4) host.firstElementChild.remove();
      i++;
    };
    setInterval(push, 2600);
  }

  /* -------------------------------- install ----------------------------- */

  let deferredPrompt = null;

  function isStandalone() {
    return matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  }

  function iosSheet() {
    const modal = $("#install-modal");
    const body = $("[data-install-body]");
    const ua = navigator.userAgent;
    const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    const src = ios ? INSTALL_STEPS.ios : INSTALL_STEPS.desktop;
    body.innerHTML = `<p>${src.body[lang]}</p><ol>${src.steps[lang].map((s) => `<li>${s}</li>`).join("")}</ol>`;
    const go = $("[data-install-go]");
    if (go) { go.hidden = true; go.setAttribute("aria-hidden", "true"); }
    modal.hidden = false;
    $("[data-install-close]").focus();
  }

  function bindInstall() {
    const modal = $("#install-modal");
    let restoreFocus = null;

    addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferredPrompt = e;
      $$("[data-install]").forEach((b) => { b.hidden = false; b.dataset.ready = "1"; });
    });

    addEventListener("appinstalled", () => {
      deferredPrompt = null;
      $$("[data-install]").forEach((b) => { b.hidden = true; });
    });

    const open = () => (deferredPrompt ? null : iosSheet());
    $$("[data-install]").forEach((b) => b.addEventListener("click", open));

    $("[data-install-go]").addEventListener("click", async () => {
      if (!deferredPrompt) { iosSheet(); return; }
      deferredPrompt.prompt();
      const choice = await deferredPrompt.userChoice.catch(() => null);
      deferredPrompt = null;
      if (choice && choice.outcome === "accepted") $$("[data-install]").forEach((b) => { b.hidden = true; });
    });

    const close = () => {
      modal.hidden = true;
      if (restoreFocus) restoreFocus.focus();
    };
    $("[data-install-close]").addEventListener("click", close);
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
    addEventListener("keydown", (e) => {
      if (modal.hidden) return;
      if (e.key === "Escape") { close(); return; }
      if (e.key !== "Tab") return;
      const focusables = $$('button, a[href], [tabindex]:not([tabindex="-1"])', modal).filter((el) => el.offsetParent !== null);
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });

    const observer = new MutationObserver(() => {
      if (!modal.hidden) {
        restoreFocus = document.activeElement;
        const first = $("[data-install-close]");
        if (first) first.focus();
      }
    });
    observer.observe(modal, { attributes: true, attributeFilter: ["hidden"] });

    if (isStandalone()) $$("[data-install]").forEach((b) => { b.hidden = true; });
  }

  /* --------------------------------- theme -------------------------------- */

  const THEME_KEY = "hadj.theme";

  function setTheme(theme) {
    if (theme === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    try { localStorage.setItem(THEME_KEY, theme); } catch (_) {}
  }

  function bindTheme() {
    let storedTheme = null;
    try { storedTheme = localStorage.getItem(THEME_KEY); } catch (_) {}
    if (!storedTheme && matchMedia("(prefers-color-scheme: light)").matches) {
      storedTheme = "light";
    }
    if (storedTheme) setTheme(storedTheme);

    const toggleBtn = $("[data-theme-toggle]");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        const isLight = document.documentElement.getAttribute("data-theme") === "light";
        setTheme(isLight ? "dark" : "light");
      });
    }
  }

  /* --------------------------------- launcher -------------------------------- */

  function bindLauncher() {
    const isLocal = location.hostname === "127.0.0.1" || location.hostname === "localhost";

    $$('[data-action="launch-app"]').forEach((btn) => {
      btn.addEventListener("click", async () => {

        if (isLocal) {
          // Local mode: try the web_server.py /api/launch endpoint
          try {
            const res = await fetch("/api/launch").then((r) => r.json()).catch(() => null);
            if (res && res.success) {
              if (res.alreadyRunning) {
                alert("✅ HADJ NO-TOUCH AI est déjà actif et en cours d'exécution sur votre PC !");
              } else {
                alert("🚀 Lancement effectué avec succès !\n\nHADJ NO-TOUCH AI est en cours de démarrage sur votre ordinateur.");
              }
              return;
            }
          } catch (_) {}

          // Fallback: check companion server directly
          try {
            const res8766 = await fetch("http://127.0.0.1:8766/status", { mode: "cors" }).catch(() => null);
            if (res8766 && res8766.ok) {
              alert("✅ HADJ NO-TOUCH AI est déjà actif et en cours d'exécution sur votre PC !");
              return;
            }
          } catch (_) {}

          alert("💡 Pour lancer HADJ : double-cliquez sur launch.bat dans votre dossier de projet.");

        } else {
          // Vercel / Remote mode: show installation instructions
          alert("💻 HADJ NO-TOUCH OFFLINE AI est une application de bureau Windows.\n\n" +
            "Pour l'utiliser :\n" +
            "1️⃣  Téléchargez ou clonez le projet sur votre PC.\n" +
            "2️⃣  Exécutez launch.bat (ou : python main.py)\n" +
            "3️⃣  Lancez le serveur local : python web_server.py\n" +
            "4️⃣  Ouvrez http://127.0.0.1:8000 sur votre machine.\n\n" +
            "ℹ️  Cette page de présentation est déployée sur Vercel. Le contrôle s'exécute 100% en local, hors ligne.");
        }
      });
    });
  }

  /* --------------------------------- boot -------------------------------- */

  function registerSW() {
    if (!("serviceWorker" in navigator) || location.protocol === "file:") return;
    addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => { /* offline cache unavailable */ });
    });
  }

  function init() {
    let stored = null;
    try { stored = localStorage.getItem(LANG_KEY); } catch (_) { stored = null; }
    setLang(stored || "fr", false);

    $$(".lang button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang, true)));
    bindTheme();
    bindTabs();
    bindNav();
    bindCopy();
    bindInstall();
    bindLauncher();
    runLog();
    registerSW();

    $("[data-top]").addEventListener("click", () => scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" }));
  }

  if (document.readyState === "loading") addEventListener("DOMContentLoaded", init);
  else init();
})();
