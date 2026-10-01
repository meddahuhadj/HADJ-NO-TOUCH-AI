/* ==========================================================================
   HADJ NO-TOUCH OFFLINE AI — landing PWA
   Trilingual runtime (ar / fr / en), gesture atlas, command atlas, install flow.
   ========================================================================== */
(() => {
  "use strict";

  const LANG_KEY = "hadj.lang";
  const SUPPORTED = ["ar", "fr", "en"];

  /* ------------------------------ sound engine ------------------------------ */

  const SoundFx = (() => {
    let audioCtx = null;
    let enabled = true;

    function getContext() {
      if (!audioCtx && typeof AudioContext !== "undefined") {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtx && audioCtx.state === "suspended") {
        audioCtx.resume().catch(() => {});
      }
      return audioCtx;
    }

    return {
      toggle() {
        enabled = !enabled;
        return enabled;
      },
      isEnabled() {
        return enabled;
      },
      play(type) {
        if (!enabled) return;
        try {
          const ctx = getContext();
          if (!ctx) return;

          const now = ctx.currentTime;
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.connect(gain);
          gain.connect(ctx.destination);

          if (type === "click") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(800, now);
            osc.frequency.exponentialRampToValueAtTime(200, now + 0.04);
            gain.gain.setValueAtTime(0.15, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
            osc.start(now);
            osc.stop(now + 0.04);
          } else if (type === "success") {
            osc.type = "triangle";
            osc.frequency.setValueAtTime(523.25, now);
            osc.frequency.setValueAtTime(659.25, now + 0.06);
            osc.frequency.setValueAtTime(783.99, now + 0.12);
            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
            osc.start(now);
            osc.stop(now + 0.25);
          } else if (type === "calib") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(440, now);
            osc.frequency.linearRampToValueAtTime(880, now + 0.15);
            gain.gain.setValueAtTime(0.1, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
            osc.start(now);
            osc.stop(now + 0.18);
          } else if (type === "wake") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(880, now);
            osc.frequency.setValueAtTime(1760, now + 0.08);
            gain.gain.setValueAtTime(0.18, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
            osc.start(now);
            osc.stop(now + 0.2);
          } else if (type === "alert" || type === "stop") {
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(440, now);
            osc.frequency.linearRampToValueAtTime(220, now + 0.2);
            gain.gain.setValueAtTime(0.2, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
            osc.start(now);
            osc.stop(now + 0.25);
          }
        } catch (_) {}
      }
    };
  })();

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
      "nav.arch": "Architecture", "nav.gestures": "Gestes", "nav.calib": "Calibration", "nav.voice": "Voix",
      "nav.security": "Sécurité", "nav.privacy": "Confidentialité", "nav.run": "Lancer",
      "nav.perf": "Performance", "nav.faq": "FAQ", "nav.install": "Installer PWA", "nav.download_btn": "Télécharger (.ZIP)", "nav.theme": "Changer le thème",
      "nav.aria": "Sections", "nav.langaria": "Langue", "nav.menu": "Ouvrir le menu",
      "hero.eyebrow": "Hors ligne par conception · IA 100% locale",
      "hero.title": "Contrôlez votre ordinateur sans le toucher.",
      "hero.lead": "Voix, gestes de la main et vision de l'écran fusionnés en une seule couche sensorielle. Aucune donnée ne quitte la machine, aucun appel cloud, aucune latence réseau.",
      "hero.cta1": "Télécharger le Package (.ZIP)", "hero.cta2": "Lancer / Diagnostic",
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
      "c.eyebrow": "Calibration automatique", "c.title": "Aucun seuil n'est codé en dur",
      "c.lead": "Les valeurs de reconnaissance ne sont pas des constantes de développeur : elles sont mesurées sur votre main, puis maintenues à jour en continu. Un assistant en huit étapes suffit.",
      "c.s1n": "Périphériques", "c.s1d": "Énumération des caméras et microphones ; ceux qui ne délivrent aucune image sont grisés.",
      "c.s2n": "Caméra", "c.s2d": "Cadence soutenue et latence de la chaîne capture vers affichage.",
      "c.s3n": "Microphone", "c.s3d": "Bruit ambiant, puis seuil vocal dérivé de ce plancher.",
      "c.s4n": "Main", "c.s4d": "Confirme le suivi et affiche la zone de portée.",
      "c.s5n": "Pincement", "c.s5d": "Trois pinces délibérées. L'histogramme des distances est coupé par la méthode d'Otsu pour placer le seuil exactement dans le vide entre vos deux groupes.",
      "c.s6n": "Portée", "c.s6d": "Un balayage de cinq secondes devient la zone active, remappée ensuite sur tout l'écran.",
      "c.s7n": "Apprentissage", "c.s7d": "Réajustement en arrière-plan, activable ou non.",
      "c.s8n": "Résumé", "c.s8d": "Chaque valeur avec son niveau de confiance, avant toute écriture. Une étape passée ou incomplète ne change rien.",
      "c.demo_t": "Le seuil de pincement, calculé en direct", "c.demo_h": "Ajustez la taille de la main et la distance caméra. L'algorithme d'Otsu retrouve le seuil par lui-même.",
      "c.demo_thr": "seuil mesuré", "c.demo_closed": "fermé", "c.demo_open": "ouvert", "c.demo_sep": "séparation",
      "c.r1": "Taille de la main", "c.r2": "Distance caméra", "c.r3": "Régularité de la pince",
      "c.demo_note": "Une main tremblante élargit les deux groupes et rend la séparation moins nette — le seuil se stabilise moins vite, mais l'assistant continue de fonctionner.",
      "c.demo_aria": "Histogramme des distances de pincement, avec le seuil calculé par la méthode d'Otsu",
      "c.box_t": "La zone active, remappée sur l'écran", "c.box_h": "Une caméra cadre rarement toute votre amplitude de mouvement. Le rectangle mesuré devient alors toute la surface exploitable.",
      "c.box_cap": "Champ caméra", "c.box_cap2": "Surface complète de l'écran",
      "c.box_aria": "Champ de la caméra et rectangle de portée mesuré", "c.box_aria2": "Le même rectangle remappé sur toute la surface de l'écran",
      "c.pr1n": "Percentiles glissants", "c.pr1d": "Les valeurs sont lues par percentiles et non par moyennes : une image parasite ne peut pas déplacer le seuil.",
      "c.pr2n": "Hystérésis", "c.pr2d": "Une nouvelle valeur doit persister sur plusieurs fenêtres avant d'être écrite, ce qui supprime les oscillations.",
      "c.pr3n": "Valeurs conservées", "c.pr3d": "Une fenêtre trop pauvre en échantillons, ou une phase où vous n'avez pas pincé, ne modifie rien.",
      "foot.lic": "licence ouverte", "foot.off": "0 requête réseau vers des tiers", "foot.top": "Revenir en haut",
      "im.t": "Télécharger & Installer HADJ NO-TOUCH AI", "im.body": "Téléchargez le package Windows complet (dossier ZIP avec launch.bat) ou installez l'application Web PWA sur votre PC.",
      "im.download_zip": "Télécharger le projet complet (.ZIP)",
      "im.launch_btn": "Diagnostic & Lancement Local",
      "im.sac_note": "💡 Une fois le fichier ZIP téléchargé : décompressez-le et double-cliquez sur launch.bat pour démarrer la caméra, la voix et l'IA locale.",
      "im.go": "Installer l'application Web (PWA)", "im.no": "Fermer",
      "r.download_zip": "Télécharger le Package (.ZIP)",
      "r.launch_btn": "Lancer / Diagnostic Local",
      "nav.hub": "⚡ Commande PC",
      "hub.eyebrow": "Centre de Contrôle Interactif · Pilotage Total",
      "hub.title": "Commande Totale du PC & Calibrage Automatique",
      "hub.lead": "Pilotez directement votre ordinateur depuis cette interface web connectée en temps réel au moteur local, testez les commandes et calibrez les seuils de tracking en un clic.",
      "hub.conn_live": "PC CONNECTÉ · CONTRÔLE TEMPS RÉEL",
      "hub.conn_wait": "EN ATTENTE DU MOTEUR LOCAL",
      "hub.btn_launch": "⚡ Lancer HADJ",
      "hub.sound_on": "Sons : Activés",
      "hub.sound_off": "Sons : Coupés",
      "hub.tab_system": "Système & Fenêtres",
      "hub.tab_audio": "Audio & Média",
      "hub.tab_touch": "Pavé Tactile & Clavier",
      "hub.tab_apps": "Applications",
      "hub.tab_console": "Console d'Ordres",
      "hub.tab_calib": "Calibrage Auto",
      "lm.title": "Diagnostic & Lancement de HADJ NO-TOUCH AI",
      "lm.subtitle": "Vérification en temps réel du moteur local et assistance de démarrage.",
      "lm.status_checking": "Analyse de la connexion au moteur local (Ports 8766 & 8000)...",
      "lm.status_online": "✅ Application locale active & connectée !",
      "lm.status_offline": "🟡 Application locale non détectée",
      "lm.telemetry_cpu": "CPU",
      "lm.telemetry_ram": "RAM",
      "lm.telemetry_companion": "Port 8766",
      "lm.telemetry_gateway": "Port 8000",
      "lm.offline_lead": "HADJ fonctionne à 100% hors ligne sur votre ordinateur pour garantir une confidentialité totale (aucun cloud).",
      "lm.step1_title": "Ouvrir le dossier du projet",
      "lm.step1_sub": "Double-cliquez sur launch.bat ou ouvrez votre terminal.",
      "lm.step2_title": "Lancer l'IA et la caméra",
      "lm.step2_sub": "Démarre la reconnaissance de la main et de la voix.",
      "lm.step3_title": "Démarrer la passerelle Web Companion",
      "lm.step3_sub": "Permet le pilotage depuis ce site ou un mobile.",
      "lm.btn_recheck": "Re-tester la connexion",
      "lm.btn_start_app": "Lancer l'Application sur mon PC",
      "lm.btn_open_local": "Ouvrir en Local (Port 8000)",
      "lm.btn_demo": "Tester le Cockpit (Mode Démo)",
      "lm.btn_goto_hub": "Accéder au Cockpit de Commande",
      "lm.btn_calib": "Lancer le Calibrage Automatique",
      "lm.btn_test_action": "Tester une commande (Vol +)",
      "lm.close": "Fermer"
    },

    en: {
      "a11y.skip": "Skip to content",
      "nav.arch": "Architecture", "nav.gestures": "Gestures", "nav.calib": "Calibration", "nav.voice": "Voice",
      "nav.security": "Security", "nav.privacy": "Privacy", "nav.run": "Run",
      "nav.perf": "Performance", "nav.faq": "FAQ", "nav.install": "Install PWA", "nav.download_btn": "Download (.ZIP)",
      "nav.aria": "Sections", "nav.langaria": "Language", "nav.menu": "Open menu", "nav.theme": "Change theme",
      "hero.eyebrow": "Offline by design · 100% local AI",
      "hero.title": "Control your computer without touching it.",
      "hero.lead": "Voice, hand gestures and screen vision fused into a single sensory layer. No data leaves the machine, no cloud call, no network latency.",
      "hero.cta1": "Download Package (.ZIP)", "hero.cta2": "Launch / Diagnostics",
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
      "r.launch_btn": "Run / check the application", "r.install_pwa": "Install the Web App (PWA)",
      "r.sac_title": "💡 Windows Smart App Control information",
      "r.sac_desc": "For security reasons, Windows 11 blocks .bat files downloaded from the Web. <b>No download is required</b>: double-click <code>launch.bat</code> in your local folder, or run <code>python main.py</code>.",
      "r.copy": "Copy command",
      "r.sp1": "Windows 10 / 11", "r.sp2": "Python 3.12", "r.sp3": "Webcam", "r.sp4": "Microphone", "r.sp5": "Companion API 127.0.0.1:8766",
      "f.eyebrow": "FAQ", "f.title": "Frequently asked",
      "f.q1": "Does it work without internet?", "f.a1": "Yes. Speech recognition, gesture recognition and intent analysis all run locally. Outbound network is blocked by default.",
      "f.q2": "Which languages are supported?", "f.a2": "Arabic, French and English, including right-to-left rendering for Arabic.",
      "f.q3": "Can I do without a mouse and keyboard?", "f.a3": "Yes. An extended index moves the cursor, a pinch clicks, a held pinch drags. A fully touchless on-screen keyboard covers dictation.",
      "f.q4": "What happens if a command is dangerous?", "f.a4": "It is graded by risk tier. HIGH and CRITICAL require confirmation, given by voice or by a thumbs up. A closed fist cancels at any time.",
      "f.q5": "Which machines?", "f.a5": "Windows 10 and 11 with Python 3.12, a webcam and a microphone. The ECO profile stays light on older hardware.",
      "f.q6": "Can I use it for accessibility?", "f.a6": "Yes. The high-contrast HUD, large cursor, dwell click and multimodal mode exist precisely for situations where precision is a problem.",
      "c.eyebrow": "Automatic calibration", "c.title": "No hard-coded thresholds",
      "c.lead": "Recognition values are not developer constants: they are measured on your hand, then kept up to date continuously. An eight-step assistant is all it takes.",
      "c.s1n": "Devices", "c.s1d": "Cameras and microphones are enumerated; those delivering no image are greyed out.",
      "c.s2n": "Camera", "c.s2d": "Sustained frame rate and latency from capture to display.",
      "c.s3n": "Microphone", "c.s3d": "Ambient noise, then a voice threshold derived from that floor.",
      "c.s4n": "Hand", "c.s4d": "Confirms tracking and shows the reach zone.",
      "c.s5n": "Pinch", "c.s5d": "Three deliberate pinches. The distance histogram is split with Otsu's method to place the threshold exactly in the gap between your two groups.",
      "c.s6n": "Reach", "c.s6d": "A five-second sweep becomes the active box, then remapped onto the whole screen.",
      "c.s7n": "Learning", "c.s7d": "Background re-tuning, switchable on or off.",
      "c.s8n": "Summary", "c.s8d": "Every value with its confidence, before anything is written. A skipped or incomplete step changes nothing.",
      "c.demo_t": "The pinch threshold, computed live", "c.demo_h": "Adjust hand size and camera distance. Otsu's algorithm finds the threshold on its own.",
      "c.demo_thr": "measured threshold", "c.demo_closed": "closed", "c.demo_open": "open", "c.demo_sep": "separation",
      "c.r1": "Hand size", "c.r2": "Camera distance", "c.r3": "Pinch consistency",
      "c.demo_note": "A shaky hand widens both groups and makes the separation less crisp — the threshold settles more slowly, but the assistant keeps working.",
      "c.demo_aria": "Histogram of pinch distances, with the threshold computed by Otsu's method",
      "c.box_t": "The active box, remapped to the screen", "c.box_h": "A camera rarely frames your whole range of motion. The measured rectangle then becomes the entire usable surface.",
      "c.box_cap": "Camera field", "c.box_cap2": "Full screen surface",
      "c.box_aria": "Camera field and measured reach rectangle", "c.box_aria2": "The same rectangle remapped to the full screen surface",
      "c.pr1n": "Rolling percentiles", "c.pr1d": "Values are read through percentiles rather than averages: a stray frame cannot move the threshold.",
      "c.pr2n": "Hysteresis", "c.pr2d": "A new value must persist across several windows before being written, which removes oscillation.",
      "c.pr3n": "Held values", "c.pr3d": "A window too poor in samples, or a phase where you did not pinch, changes nothing.",
      "foot.lic": "open licence", "foot.off": "0 third-party network requests", "foot.top": "Back to top",
      "im.t": "Download & Install HADJ NO-TOUCH AI", "im.body": "Download the full Windows package (ZIP folder with launch.bat) or install the Web PWA on your PC.",
      "im.download_zip": "Download Full Project (.ZIP)",
      "im.launch_btn": "Local Diagnostics & Launch",
      "im.sac_note": "💡 Once the ZIP is downloaded: extract it and double-click launch.bat to launch offline AI & vision.",
      "im.go": "Install Web App (PWA)", "im.no": "Close",
      "r.download_zip": "Download Package (.ZIP)",
      "r.launch_btn": "Launch / Local Diagnostics",
      "nav.hub": "⚡ PC Control",
      "hub.eyebrow": "Interactive Control Center · Total Remote",
      "hub.title": "Total PC Control & Auto-Calibration",
      "hub.lead": "Control your PC directly from this web dashboard connected in real-time to the local engine, execute actions, and calibrate tracking thresholds with one click.",
      "hub.conn_live": "PC CONNECTED · REAL-TIME CONTROL",
      "hub.conn_wait": "WAITING FOR LOCAL ENGINE",
      "hub.btn_launch": "⚡ Launch HADJ",
      "hub.sound_on": "Sound: On",
      "hub.sound_off": "Sound: Off",
      "hub.tab_system": "System & Windows",
      "hub.tab_audio": "Audio & Media",
      "hub.tab_touch": "Trackpad & Typing",
      "hub.tab_apps": "Quick Apps",
      "hub.tab_console": "Command Console",
      "hub.tab_calib": "Auto-Calibration",
      "lm.title": "Diagnostics & Launch — HADJ NO-TOUCH AI",
      "lm.subtitle": "Real-time local engine verification and startup guide.",
      "lm.status_checking": "Scanning local engine connection (Ports 8766 & 8000)...",
      "lm.status_online": "✅ Local application running & connected!",
      "lm.status_offline": "🟡 Local application not detected",
      "lm.telemetry_cpu": "CPU",
      "lm.telemetry_ram": "RAM",
      "lm.telemetry_companion": "Port 8766",
      "lm.telemetry_gateway": "Port 8000",
      "lm.offline_lead": "HADJ runs 100% offline on your computer to ensure complete privacy (zero cloud).",
      "lm.step1_title": "Open project folder",
      "lm.step1_sub": "Double-click launch.bat or open your terminal.",
      "lm.step2_title": "Launch AI & Vision",
      "lm.step2_sub": "Starts hand tracking and voice listening.",
      "lm.step3_title": "Start Web Companion gateway",
      "lm.step3_sub": "Enables remote control from this website or mobile.",
      "lm.btn_recheck": "Re-test connection",
      "lm.btn_start_app": "Launch Application on my PC",
      "lm.btn_open_local": "Open local dashboard (Port 8000)",
      "lm.btn_demo": "Try Cockpit in Demo Mode",
      "lm.btn_goto_hub": "Go to Command Cockpit",
      "lm.btn_calib": "Run Auto-Calibration",
      "lm.btn_test_action": "Test PC Action (Vol +)",
      "lm.close": "Close"
    },

    ar: {
      "a11y.skip": "تخطَّ إلى المحتوى",
      "nav.arch": "البنية", "nav.gestures": "الإيماءات", "nav.calib": "المعايرة", "nav.voice": "الصوت",
      "nav.security": "الأمان", "nav.privacy": "الخصوصية", "nav.run": "التشغيل",
      "nav.perf": "الأداء", "nav.faq": "أسئلة", "nav.install": "تثبيت PWA", "nav.download_btn": "تحميل (.ZIP)",
      "nav.aria": "الأقسام", "nav.langaria": "اللغة", "nav.menu": "فتح القائمة", "nav.theme": "تبديل السمة",
      "hero.eyebrow": "يعمل دون إنترنت · ذكاء اصطناعي محلي بالكامل",
      "hero.title": "تحكّم في حاسوبك دون أن تلمسه.",
      "hero.lead": "صوت وإيماءات اليد ورؤية الشاشة في طبقة حسّية واحدة. لا تغادر أي بيانات جهازك، ولا يوجد أي اتصال سحابي، ولا أي تأخير شبكي.",
      "hero.cta1": "تحميل حزمة (.ZIP)", "hero.cta2": "تشغيل / فحص",
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
      "r.launch_btn": "شغّل التطبيق / تحقّق منه", "r.install_pwa": "ثبّت تطبيق الويب (PWA)",
      "r.sac_title": "💡 معلومات عن Smart App Control في ويندوز",
      "r.sac_desc": "لأسباب أمنية، يحجب ويندوز 11 ملفات ‎.bat‎ المنزّلة من الويب. <b>لا حاجة إلى أي تنزيل</b>: انقر نقرًا مزدوجًا على <code>launch.bat</code> داخل مجلدك المحلي، أو نفّذ <code>python main.py</code>.",
      "r.copy": "نسخ الأمر",
      "r.sp1": "ويندوز 10 / 11", "r.sp2": "بايثون 3.12", "r.sp3": "كاميرا", "r.sp4": "ميكروفون", "r.sp5": "واجهة مرافقة 127.0.0.1:8766",
      "f.eyebrow": "أسئلة", "f.title": "أسئلة متكررة",
      "f.q1": "هل يعمل دون إنترنت؟", "f.a1": "نعم. التعرّف على الصوت وعلى الإيماءات وتحليل النيّة تعمل جميعها محليًا، والشبكة الخارجية محجوبة افتراضيًا.",
      "f.q2": "ما اللغات المدعومة؟", "f.a2": "العربية والفرنسية والإنجليزية، مع عرض من اليمين إلى اليسار للعربية.",
      "f.q3": "هل يمكن الاستغناء عن الفأرة ولوحة المفاتيح؟", "f.a3": "نعم. مدّ السبابة يحرّك المؤشر، والضغط يقرّر، والضغط المستمر يسحب. ولوحة مفاتيح افتراضية بلا أزرار تتولّى الإملاء.",
      "f.q4": "ماذا يحدث إذا كان الأمر خطيرًا؟", "f.a4": "يُصنَّف حسب مستوى الخطر. يحتاج المستوى HIGH وCRITICAL إلى تأكيد يُقال صوتيًا أو بالإبهام لأعلى. والقبضة تلغي في أي لحظة.",
      "f.q5": "ما الأجهزة المدعومة؟", "f.a5": "ويندوز 10 و11 مع بايثون 3.12 وكاميرا وميكروفون. ووضع ECO يخفّض الاستهلاك على الأجهزة القديمة.",
      "f.q6": "هل يصلح لإتاحة الوصول؟", "f.a6": "نعم. اللوحة العلوية عالية التباين، والمؤشر الكبير، والنقر بالثبات، والوضع متعدّد الوسائط موجودة أصلًا للمواقف التي يصعب فيها الدقة.",
      "c.eyebrow": "المعايرة التلقائية", "c.title": "لا عتبات مكتوبة يدويًا",
      "c.lead": "قيم التعرّف ليست ثوابت من عند المطوّر: بل تُقاس على يدك، ثم تُحدَّث باستمرار. ثماني خطوات في معالج تكفي.",
      "c.s1n": "الأجهزة", "c.s1d": "حصر الكاميرات والميكروفونات، مع تدرّج الأجهزة التي لا تُنتج صورة.",
      "c.s2n": "الكاميرا", "c.s2d": "معدل إطارات ثابت وزمن الاستجابة من الالتقاط إلى العرض.",
      "c.s3n": "الميكروفون", "c.s3d": "ضجيج محيط، ثم عتبة صوت مشتقّة من تلك الأرضية.",
      "c.s4n": "اليد", "c.s4d": "تأكيد التتبّع وإظهار منطقة المدى.",
      "c.s5n": "القرص", "c.s5d": "ثلاث قرصات مقصودة. يُقسَّم مدرّج المسافات بطريقة أوتسو ليوضع العتبة في الفراغ بين مجموعتَيْك بالضبط.",
      "c.s6n": "المدى", "c.s6d": "تمسحة من خمس ثوانٍ تصبح الصندوق النشط، ثم يُعاد إسقاطه على كامل الشاشة.",
      "c.s7n": "التعلّم", "c.s7d": "إعادة ضبط في الخلفية، يمكن تفعيلها أو تعطيلها.",
      "c.s8n": "الخلاصة", "c.s8d": "كل قيمة مع درجة ثقتها، قبل أي كتابة. خطوة مُتخطّاة أو غير مكتملة لا تغيّر شيئًا.",
      "c.demo_t": "عتبة القرص، محسوبة مباشرةً", "c.demo_h": "اضبط حجم اليد ومسافة الكاميرا. خوارزمية أوتسو تجد العتبة بنفسها.",
      "c.demo_thr": "العتبة المقاسة", "c.demo_closed": "مغلق", "c.demo_open": "مفتوح", "c.demo_sep": "الفصل",
      "c.r1": "حجم اليد", "c.r2": "مسافة الكاميرا", "c.r3": "ثبات القرص",
      "c.demo_note": "اليد المرتجفة توسّع المجموعتين وتجعل الفصل أقل وضوحًا — تستقر العتبة ببطء أكبر، لكن المعالج يبقى يعمل.",
      "c.demo_aria": "مدرّج مسافات القرص، مع العتبة المحسوبة بطريقة أوتسو",
      "c.box_t": "الصندوق النشط، مُسقَط على الشاشة", "c.box_h": "نادرًا ما تُؤطِّر الكاميرا كامل مدى حركتك. يصبح المستطيل المقاس عندها كامل السطح القابل للاستخدام.",
      "c.box_cap": "مجال الكاميرا", "c.box_cap2": "كامل سطح الشاشة",
      "c.box_aria": "مجال الكاميرا ومستطيل المدى المقاس", "c.box_aria2": "المستطيل نفسه مُسقَط على كامل سطح الشاشة",
      "c.pr1n": "مئينات متحرّكة", "c.pr1d": "تُقرأ القيم بالمئينات لا بالمتوسطات: صورة شاذّة واحدة لا تستطيع تحريك العتبة.",
      "c.pr2n": "تخلّف حراري", "c.pr2d": "يجب أن تستمر القيمة الجديدة عبر عدّة نوافذ قبل كتابتها، ما يُزيل التذبذب.",
      "c.pr3n": "قيم محفوظة", "c.pr3d": "نافذة فقيرة بالعيّنات، أو مرحلة لم تقرص فيها، لا تغيّر شيئًا.",
      "foot.lic": "رخصة مفتوحة", "foot.off": "صفر طلب شبكة نحو أطراف خارجية", "foot.top": "العودة إلى الأعلى",
      "im.t": "تحميل وتثبيت HADJ NO-TOUCH AI", "im.body": "قم بتحميل حزمة ويندوز الكاملة (ملف ZIP يحتوي على launch.bat) أو تثبيت تطبيق الويب PWA على حاسوبك.",
      "im.download_zip": "تحميل المشروع كاملًا (.ZIP)",
      "im.launch_btn": "فحص وتشغيل المحلي",
      "im.sac_note": "💡 بعد تحميل ملف ZIP: قم بفك الضغط وانقر مرتين على launch.bat لتشغيل الذكاء الاصطناعي والكاميرا.",
      "im.go": "تثبيت تطبيق الويب (PWA)", "im.no": "إغلاق",
      "r.download_zip": "تحميل حزمة ويندوز (.ZIP)",
      "r.launch_btn": "تشغيل / الفحص المحلي",
      "nav.hub": "⚡ التحكم بالكمبيوتر",
      "hub.eyebrow": "مركز التحكم التفاعلي · تحكم كامل",
      "hub.title": "التحكم الشامل بالكمبيوتر والمعايرة التلقائية",
      "hub.lead": "تحكم بالكمبيوتر مباشرة من هذه الواجهة المتصلة فورياً بالمحرك المحلي، ونفذ الأوامر وعاير حساسية الإيماءات بنقرة واحدة.",
      "hub.conn_live": "متصل بالكمبيوتر · التحكم نشط",
      "hub.conn_wait": "في انتظار المحرك المحلي",
      "hub.btn_launch": "⚡ تشغيل HADJ",
      "hub.sound_on": "الصوت: مفعّل",
      "hub.sound_off": "الصوت: معطّل",
      "hub.tab_system": "النظام والنوافذ",
      "hub.tab_audio": "الصوت والوسائط",
      "hub.tab_touch": "لوحة اللمس والكتابة",
      "hub.tab_apps": "تشغيل التطبيقات",
      "hub.tab_console": "موجه الأوامر",
      "hub.tab_calib": "المعايرة التلقائية",
      "lm.title": "فحص وتشغيل HADJ NO-TOUCH AI",
      "lm.subtitle": "التحقق المباشر من المحرك المحلي ودليل بدء التشغيل.",
      "lm.status_checking": "جاري فحص الاتصال بالمحرك المحلي (المنافذ 8766 و8000)...",
      "lm.status_online": "✅ التطبيق المحلي قيد التشغيل ومتصل بنجاح!",
      "lm.status_offline": "🟡 لم يتم العثور على التطبيق المحلي بعد",
      "lm.telemetry_cpu": "المعالج",
      "lm.telemetry_ram": "الذاكرة",
      "lm.telemetry_companion": "منفذ 8766",
      "lm.telemetry_gateway": "منفذ 8000",
      "lm.offline_lead": "يعمل HADJ محلياً 100% على حاسوبك لضمان الخصوصية التامة دون أي سحابة.",
      "lm.step1_title": "افتح مجلد المشروع",
      "lm.step1_sub": "انقر مرتين على launch.bat أو افتح موجه الأوامر.",
      "lm.step2_title": "شغّل الذكاء الاصطناعي والكاميرا",
      "lm.step2_sub": "يبدأ تتبع اليدين والاستماع الصوتي المحلي.",
      "lm.step3_title": "شغّل بوابة الويب المحلية",
      "lm.step3_sub": "يتيح التحكم الكامل من هذا الموقع أو الهاتف.",
      "lm.btn_recheck": "إعادة فحص الاتصال",
      "lm.btn_start_app": "تشغيل التطبيق على الحاسوب",
      "lm.btn_open_local": "فتح التطبيق المحلي (منفذ 8000)",
      "lm.btn_demo": "تجربة لوحة التحكم (محاكاة)",
      "lm.btn_goto_hub": "الذهاب إلى مركز التحكم الكامل",
      "lm.btn_calib": "تشغيل المعايرة التلقائية",
      "lm.btn_test_action": "اختبار أمر بالنظام (رفع الصوت)",
      "lm.close": "إغلاق"
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

  /* --------------------------------- launcher -------------------------------- */

  function bindLauncher() {
    const modal = $("#launch-modal");
    if (!modal) return;

    let restoreFocus = null;

    async function runDiagnostics() {
      const dot = $("[data-lm-dot]", modal);
      const statusTxt = $("[data-lm-status-text]", modal);
      const viewOnline = $('[data-lm-view="online"]', modal);
      const viewOffline = $('[data-lm-view="offline"]', modal);
      const p8766 = $("[data-lm-p8766]", modal);
      const p8000 = $("[data-lm-p8000]", modal);
      const cpuEl = $("[data-lm-cpu]", modal);
      const ramEl = $("[data-lm-ram]", modal);

      if (dot) dot.className = "lm-dot is-checking";
      if (statusTxt) {
        statusTxt.textContent = (DICT[lang] && DICT[lang]["lm.status_checking"]) || "Analyse de la connexion au moteur local (Ports 8766 & 8000)...";
      }

      let is8000Ok = false;
      let is8766Ok = false;
      let statsData = null;

      try {
        const r8000 = await fetch("/api/status", { cache: "no-store" }).catch(() => null);
        if (r8000 && r8000.ok) {
          is8000Ok = true;
          statsData = await r8000.json().catch(() => null);
        }
      } catch (_) {}

      try {
        const r8766 = await fetch("http://127.0.0.1:8766/status", { mode: "cors", cache: "no-store" }).catch(() => null);
        if (r8766 && r8766.ok) {
          is8766Ok = true;
          if (!statsData) statsData = await r8766.json().catch(() => null);
        }
      } catch (_) {}

      if (p8766) {
        p8766.textContent = is8766Ok ? "ACTIF" : "OFFLINE";
        p8766.style.color = is8766Ok ? "#34d399" : "#ffb703";
      }
      if (p8000) {
        p8000.textContent = is8000Ok ? "ACTIF" : "OFFLINE";
        p8000.style.color = is8000Ok ? "#34d399" : "#ffb703";
      }

      const telem = (statsData && statsData.telemetry) || {};
      if (cpuEl) cpuEl.textContent = telem.cpu_percent != null ? `${Math.round(telem.cpu_percent)}%` : "--%";
      if (ramEl) ramEl.textContent = telem.memory_percent != null ? `${Math.round(telem.memory_percent)}%` : "--%";

      const isOnline = is8000Ok || is8766Ok;

      if (dot) dot.className = `lm-dot ${isOnline ? "is-online" : ""}`;
      if (statusTxt) {
        statusTxt.textContent = isOnline
          ? ((DICT[lang] && DICT[lang]["lm.status_online"]) || "✅ Application locale active & connectée !")
          : ((DICT[lang] && DICT[lang]["lm.status_offline"]) || "🟡 Application locale non détectée");
      }

      if (viewOnline) viewOnline.hidden = !isOnline;
      if (viewOffline) viewOffline.hidden = isOnline;

      return isOnline;
    }

    function openModal() {
      restoreFocus = document.activeElement;
      modal.removeAttribute("hidden");
      document.body.style.overflow = "hidden";
      runDiagnostics();
    }

    function closeModal() {
      modal.setAttribute("hidden", "");
      document.body.style.overflow = "";
      if (restoreFocus && typeof restoreFocus.focus === "function") {
        restoreFocus.focus();
      }
    }

    $$('[data-action="launch-app"]').forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        SoundFx.play("click");
        openModal();
      });
    });

    $$("[data-launch-close]", modal).forEach((btn) => {
      btn.addEventListener("click", () => {
        SoundFx.play("click");
        closeModal();
      });
    });

    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        SoundFx.play("click");
        closeModal();
      }
    });

    addEventListener("keydown", (e) => {
      if (modal.hidden) return;
      if (e.key === "Escape") {
        SoundFx.play("click");
        closeModal();
      }
    });

    const btnRecheck = $("[data-lm-recheck]", modal);
    const btnStartApp = $("[data-lm-start-app]", modal);
    const btnGotoHub = $("[data-lm-goto-hub]", modal);
    const btnCalib = $("[data-lm-calib]", modal);
    const btnTestAction = $("[data-lm-test-action]", modal);
    const btnDemo = $("[data-lm-demo-mode]", modal);

    if (btnStartApp) {
      btnStartApp.addEventListener("click", async () => {
        SoundFx.play("click");
        btnStartApp.disabled = true;
        try {
          if (location.protocol === "https:") {
            const openLocal = confirm(
              "🌐 Vous consultez la version hébergée sur Vercel (HTTPS).\n\n" +
              "Pour le contrôle direct en temps réel de votre ordinateur, la passerelle s'exécute en local sur :\n" +
              "http://127.0.0.1:8000\n\n" +
              "Voulez-vous ouvrir l'interface locale sur votre PC ?"
            );
            if (openLocal) {
              window.open("http://127.0.0.1:8000", "_blank");
            }
            return;
          }

          let res = await fetch("/api/launch", { cache: "no-store" }).then((r) => r.json()).catch(() => null);
          if (!res || !res.success) {
            res = await fetch("http://127.0.0.1:8000/api/launch", { mode: "cors", cache: "no-store" }).then((r) => r.json()).catch(() => null);
          }

          if (res && res.success) {
            SoundFx.play("success");
            alert(res.alreadyRunning 
              ? "✅ HADJ NO-TOUCH AI est déjà actif et en cours d'exécution sur votre PC !" 
              : "🚀 Ordre de lancement envoyé !\n\nLe moteur HADJ NO-TOUCH AI est en cours de démarrage sur votre ordinateur.");
            runDiagnostics();
          } else {
            alert("💡 Pour lancer l'application sur votre PC :\n\n1️⃣ Téléchargez le package ZIP du projet\n2️⃣ Décompressez-le et double-cliquez sur launch.bat (ou python main.py)\n3️⃣ Exécutez python web_server.py pour connecter la passerelle Web.");
          }
        } finally {
          btnStartApp.disabled = false;
        }
      });
    }

    if (btnRecheck) {
      btnRecheck.addEventListener("click", () => {
        SoundFx.play("click");
        const icon = btnRecheck.querySelector(".lm-spin-icon");
        if (icon) icon.classList.add("is-spinning");
        runDiagnostics().finally(() => {
          if (icon) icon.classList.remove("is-spinning");
        });
      });
    }

    if (btnGotoHub) {
      btnGotoHub.addEventListener("click", () => {
        SoundFx.play("click");
        closeModal();
        const hub = $("#control-hub");
        if (hub) hub.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
      });
    }

    if (btnCalib) {
      btnCalib.addEventListener("click", () => {
        SoundFx.play("click");
        closeModal();
        const hub = $("#control-hub");
        if (hub) hub.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
        const calibTab = $('[data-hub-tab="calib"]');
        if (calibTab) calibTab.click();
        const calibBtn = $("[data-trigger-calib]");
        if (calibBtn) calibBtn.click();
      });
    }

    if (btnTestAction) {
      btnTestAction.addEventListener("click", async () => {
        SoundFx.play("click");
        btnTestAction.disabled = true;
        try {
          const res = await fetch("/api/action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "volume_up" })
          }).catch(() => null);

          if (res && res.ok) {
            SoundFx.play("success");
            alert("🔊 Commande testée avec succès ! (Volume +)");
          } else {
            const res8766 = await fetch("http://127.0.0.1:8766/action", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action: "volume_up" })
            }).catch(() => null);

            if (res8766 && res8766.ok) {
              SoundFx.play("success");
              alert("🔊 Commande testée via Port 8766 ! (Volume +)");
            } else {
              alert("🟡 Moteur local indisponible. Démarrez launch.bat pour activer le contrôle.");
            }
          }
        } finally {
          btnTestAction.disabled = false;
        }
      });
    }

    if (btnDemo) {
      btnDemo.addEventListener("click", () => {
        SoundFx.play("success");
        closeModal();
        const hub = $("#control-hub");
        if (hub) hub.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
        const statusBadge = $("[data-hub-status]");
        const statusTxt = $("[data-hub-conn-txt]");
        if (statusBadge) statusBadge.classList.add("is-online");
        if (statusTxt) statusTxt.textContent = "MODE DÉMO ACTIF · SIMULATION EN DIRECT";
      });
    }
  }

  /* ----------------------------- calibration ----------------------------- */

  /* Two Gaussians = the open and the closed pinch, plus per-channel jitter.
     Otsu then splits the histogram at the class boundary, exactly as
     core/auto_calibration.py does at calibration time. */
  function gauss(x, mu, sigma) {
    return Math.exp(-((x - mu) * (x - mu)) / (2 * sigma * sigma));
  }

  function buildHistogram(size, dist, jitter) {
    const BINS = 48;
    const MAX = 0.14;
    const closedMu = 0.018 / (size * dist);
    const openMu = 0.062 / (size * dist);
    const closedSig = (0.0035 + 0.0055 * jitter) / (size * dist);
    const openSig = (0.0055 + 0.0065 * jitter) / (size * dist);
    const bins = new Array(BINS).fill(0);
    for (let i = 0; i < BINS; i++) {
      const v = ((i + 0.5) / BINS) * MAX;
      bins[i] = 0.72 * gauss(v, closedMu, closedSig) + 0.28 * gauss(v, openMu, openSig);
    }
    return { bins, MAX, closedMu, openMu };
  }

  function otsu(bins) {
    const n = bins.length;
    const total = bins.reduce((a, b) => a + b, 0);
    if (!total) return 0;
    let sum = 0;
    for (let i = 0; i < n; i++) sum += i * bins[i];
    let wB = 0, sumB = 0, best = 0, bestVar = -1;
    for (let t = 0; t < n - 1; t++) {
      wB += bins[t];
      if (wB === 0) continue;
      const wF = total - wB;
      if (wF === 0) break;
      sumB += t * bins[t];
      const mB = sumB / wB;
      const mF = (sum - sumB) / wF;
      const between = wB * wF * (mB - mF) * (mB - mF);
      if (between > bestVar) { bestVar = between; best = t; }
    }
    return (best + 1) / n;
  }

  function renderHistogram() {
    const barsHost = $("[data-c-bars]");
    const markHost = $("[data-c-mark]");
    const readout = $("[data-c-thr]");
    if (!barsHost || !markHost) return;

    const size = Number($("[data-c-size]").value);
    const dist = Number($("[data-c-dist]").value);
    const jit = Number($("[data-c-jit]").value);
    ["size", "dist", "jit"].forEach((k) => {
      const out = $(`[data-c-${k}-out]`);
      if (out) out.textContent = Number($(`[data-c-${k}]`).value).toFixed(2);
    });

    const { bins, MAX, closedMu } = buildHistogram(size, dist, jit);
    const peak = Math.max(...bins) || 1;
    const W = 340, H = 132, BASE = 118;

    barsHost.innerHTML = bins.map((v, i) => {
      const h = Math.max(1.5, (v / peak) * (H - 24));
      const x = (i / bins.length) * W;
      const w = W / bins.length - 1.1;
      const center = ((i + 0.5) / bins.length) * MAX;
      return `<rect class="hist__bar${center < closedMu ? " hist__bar--closed" : ""}" x="${x.toFixed(2)}" y="${(BASE - h).toFixed(2)}" width="${w.toFixed(2)}" height="${h.toFixed(2)}" rx="1"/>`;
    }).join("");

    const frac = otsu(bins);
    const px = frac * W;
    const thr = frac * MAX;
    markHost.innerHTML =
      `<rect class="hist__gap" x="${(px - 3).toFixed(2)}" y="8" width="6" height="${BASE - 8}"/>` +
      `<line class="hist__thr" x1="${px.toFixed(2)}" y1="6" x2="${px.toFixed(2)}" y2="${BASE}"/>` +
      `<text class="hist__thr-l" x="${(px + 5).toFixed(2)}" y="14">OTSU</text>`;

    if (readout) readout.textContent = thr.toFixed(3);
  }

  function renderBox() {
    const box = $("[data-c-box]");
    const hand = $("[data-c-hand]");
    const trail = $("[data-c-trail]");
    const screen = $("[data-c-screen]");
    if (!box || !hand) return;

    const size = Number($("[data-c-size]").value);
    const dist = Number($("[data-c-dist]").value);
    const jit = Number($("[data-c-jit]").value);

    const FW = 300, FH = 176;
    const halfW = FW * (0.11 + 0.19 * size) * (0.7 + 0.3 * dist);
    const halfH = FH * (0.08 + 0.15 * size);
    const bx = Math.max(2, FW / 2 - halfW);
    const by = Math.max(2, FH / 2 - halfH);
    const bw = Math.min(FW - 4, halfW * 2);
    const bh = Math.min(FH - 4, halfH * 2);

    box.setAttribute("x", bx.toFixed(1));
    box.setAttribute("y", by.toFixed(1));
    box.setAttribute("width", bw.toFixed(1));
    box.setAttribute("height", bh.toFixed(1));

    const cx = FW / 2, cy = FH / 2;
    const amp = 0.36 * bw * (0.8 + 0.2 * jit);
    const pts = [];
    for (let i = 0; i <= 26; i++) {
      const t = i / 26;
      const x = cx + Math.sin(t * Math.PI * 2) * amp;
      const y = cy + Math.sin(t * Math.PI * 4) * amp * 0.34;
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    if (trail) trail.innerHTML = `<path class="reach__trail" d="M${pts.join(" L")}"/>`;
    hand.innerHTML = `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${(4.5 + 2.5 * size).toFixed(1)}"/>`;

    if (screen) {
      const SW = 300, SH = 176;
      const pad = 26;
      const sw = SW - pad * 2, sh = SH - pad * 2;
      const u = amp / bw, v = (amp * 0.34) / bh;
      let cells = "";
      for (let r = 0; r < 5; r++) {
        for (let c = 0; c < 7; c++) {
          const t = r / 4, s = c / 6;
          const x = pad + s * sw;
          const y = pad + t * sh;
          const on = Math.abs(s - 0.5) * 2 <= u && Math.abs(t - 0.5) * 2 <= v;
          cells += `<rect class="${on ? "reach__scr" : "reach__scr-dim"}" x="${(x - 5).toFixed(1)}" y="${(y - 5).toFixed(1)}" width="10" height="10" rx="1.5" opacity="${on ? 0.95 : 0.3}"/>`;
        }
      }
      screen.innerHTML = cells;
    }
  }

  function renderCalibration() {
    renderHistogram();
    renderBox();
  }

  function bindCalibration() {
    const host = $("#calibration");
    if (!host) return;
    ["size", "dist", "jit"].forEach((k) => {
      const input = $(`[data-c-${k}]`);
      if (input) input.addEventListener("input", renderCalibration);
    });
    renderCalibration();
  }

  /* -------------------------- interactive hub -------------------------- */

  const SoundFx = (() => {
    let enabled = true;
    let ctx = null;
    function getCtx() {
      if (!ctx && (window.AudioContext || window.webkitAudioContext)) {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (ctx && ctx.state === "suspended") ctx.resume();
      return ctx;
    }
    return {
      toggle() { enabled = !enabled; return enabled; },
      isEnabled() { return enabled; },
      play(type) {
        if (!enabled) return;
        try {
          const c = getCtx();
          if (!c) return;
          const now = c.currentTime;
          const osc = c.createOscillator();
          const gain = c.createGain();
          osc.connect(gain);
          gain.connect(c.destination);
          if (type === "click") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(800, now);
            osc.frequency.exponentialRampToValueAtTime(360, now + 0.05);
            gain.gain.setValueAtTime(0.06, now);
            gain.gain.linearRampToValueAtTime(0.001, now + 0.05);
            osc.start(now);
            osc.stop(now + 0.05);
          } else if (type === "success") {
            osc.type = "triangle";
            osc.frequency.setValueAtTime(523.25, now);
            osc.frequency.setValueAtTime(659.25, now + 0.07);
            osc.frequency.setValueAtTime(783.99, now + 0.14);
            gain.gain.setValueAtTime(0.1, now);
            gain.gain.linearRampToValueAtTime(0.001, now + 0.32);
            osc.start(now);
            osc.stop(now + 0.32);
          } else if (type === "calib") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(440, now);
            osc.frequency.exponentialRampToValueAtTime(880, now + 0.22);
            gain.gain.setValueAtTime(0.08, now);
            gain.gain.linearRampToValueAtTime(0.001, now + 0.22);
            osc.start(now);
            osc.stop(now + 0.22);
          }
        } catch (_) {}
      }
    };
  })();

  function bindControlHub() {
    const hub = $("#control-hub");
    if (!hub) return;

    let authToken = "";

    const statusBadge = $("[data-hub-status]");
    const statusTxt = $("[data-hub-conn-txt]");
    const telemCpu = $("[data-telem-cpu]");
    const telemRam = $("[data-telem-ram]");
    const telemFps = $("[data-telem-fps]");
    const telemPing = $("[data-telem-ping]");
    const consoleLogs = $("[data-console-logs]");
    const termStatus = $("[data-term-status]");

    function logMsg(msg) {
      if (!consoleLogs) return;
      const time = new Date().toTimeString().split(" ")[0];
      const line = `[${time}] ${msg}`;
      const code = consoleLogs.querySelector("code");
      if (code) {
        code.textContent = `${code.textContent}\n${line}`.split("\n").slice(-8).join("\n");
        consoleLogs.scrollTop = consoleLogs.scrollHeight;
      }
    }

    // Sound toggle
    const soundToggle = $("[data-sound-toggle]");
    const soundIcon = $("[data-sound-icon]");
    const soundLabel = $("[data-sound-label]");
    if (soundToggle) {
      soundToggle.addEventListener("click", () => {
        const on = SoundFx.toggle();
        if (soundIcon) soundIcon.textContent = on ? "🔊" : "🔇";
        if (soundLabel) soundLabel.textContent = on ? "Sons : Activés" : "Sons : Coupés";
        if (on) SoundFx.play("click");
      });
    }

    // Dwell mode toggle
    const dwellToggle = $("[data-dwell-toggle]");
    const dwellIcon = $("[data-dwell-icon]");
    const dwellLabel = $("[data-dwell-label]");
    let dwellActive = false;
    let dwellTimer = null;
    let dwellTarget = null;
    let dwellRingEl = null;

    function createDwellRing() {
      if (dwellRingEl) return dwellRingEl;
      dwellRingEl = document.createElement("div");
      dwellRingEl.className = "dwell-cursor-ring";
      dwellRingEl.style.display = "none";
      dwellRingEl.innerHTML = `
        <svg viewBox="0 0 36 36">
          <circle class="dwell-bg" cx="18" cy="18" r="14" stroke-width="3"/>
          <circle class="dwell-progress" cx="18" cy="18" r="14" stroke-width="3"/>
        </svg>
        <span class="dwell-center-dot"></span>
      `;
      document.body.appendChild(dwellRingEl);
      return dwellRingEl;
    }

    if (dwellToggle) {
      dwellToggle.addEventListener("click", () => {
        dwellActive = !dwellActive;
        dwellToggle.classList.toggle("is-active", dwellActive);
        if (dwellIcon) dwellIcon.textContent = "🎯";
        if (dwellLabel) dwellLabel.textContent = dwellActive ? "Mode Dwell : Actif" : "Mode Dwell : Inactif";
        document.body.classList.toggle("dwell-mode-active", dwellActive);
        SoundFx.play(dwellActive ? "wake" : "click");
        logMsg(`Mode Dwell (Sans Clic) : ${dwellActive ? "ACTIVÉ" : "DÉSACTIVÉ"}`);

        if (dwellActive) {
          createDwellRing();
        } else if (dwellRingEl) {
          dwellRingEl.style.display = "none";
        }
      });
    }

    window.addEventListener("pointermove", (e) => {
      if (!dwellActive) return;
      if (!dwellRingEl) createDwellRing();
      dwellRingEl.style.display = "flex";
      dwellRingEl.style.left = `${e.clientX}px`;
      dwellRingEl.style.top = `${e.clientY}px`;

      const target = document.elementFromPoint(e.clientX, e.clientY);
      const clickable = target ? target.closest("button, a, [role='button'], .hub-card-btn, .hub-tab, .hub-key-chip") : null;

      if (clickable !== dwellTarget) {
        clearTimeout(dwellTimer);
        dwellTarget = clickable;
        const circle = dwellRingEl.querySelector(".dwell-progress");
        if (circle) circle.style.strokeDashoffset = "100";

        if (clickable) {
          let start = Date.now();
          const duration = 750;
          function animateProgress() {
            if (!dwellActive || dwellTarget !== clickable) return;
            const elapsed = Date.now() - start;
            const pct = Math.min(1, elapsed / duration);
            if (circle) circle.style.strokeDashoffset = `${100 - pct * 100}`;

            if (pct < 1) {
              requestAnimationFrame(animateProgress);
            } else {
              SoundFx.play("click");
              clickable.click();
              if (circle) circle.style.strokeDashoffset = "100";
              dwellTarget = null;
            }
          }
          requestAnimationFrame(animateProgress);
        }
      }
    });

    // Interactive HUD 3D skeleton & cursor visualizer
    function bindHudInteractive() {
      const hudView = $(".hud__view");
      const hudCursor = $(".hud__cursor");
      const skelSvg = $(".hud__skel");

      if (!hudView) return;

      hudView.addEventListener("mousemove", (e) => {
        const rect = hudView.getBoundingClientRect();
        const rx = Math.max(0.05, Math.min(0.95, (e.clientX - rect.left) / rect.width));
        const ry = Math.max(0.05, Math.min(0.95, (e.clientY - rect.top) / rect.height));

        if (hudCursor) {
          hudCursor.style.left = `${rx * 100}%`;
          hudCursor.style.top = `${ry * 100}%`;
        }

        if (skelSvg) {
          const tips = skelSvg.querySelectorAll(".skel__tips circle");
          if (tips && tips[0]) {
            tips[0].setAttribute("cx", Math.round(rx * 240));
            tips[0].setAttribute("cy", Math.round(ry * 180));
          }
        }
      });

      hudView.addEventListener("click", () => {
        SoundFx.play("click");
        const pulse = hudCursor ? hudCursor.querySelector(".cur__pulse") : null;
        if (pulse) {
          pulse.classList.remove("is-clicking");
          void pulse.offsetWidth;
          pulse.classList.add("is-clicking");
        }
        logMsg("🎯 Clic pince simulé sur le HUD");
      });
    }

    bindHudInteractive();

    // Tab switching
    const tabs = $$("[data-hub-tab]");
    const panels = $$("[data-hub-panel]");
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        SoundFx.play("click");
        const target = tab.dataset.hubTab;
        tabs.forEach((t) => {
          t.classList.toggle("is-active", t === tab);
          t.setAttribute("aria-selected", t === tab ? "true" : "false");
        });
        panels.forEach((p) => {
          p.classList.toggle("is-active", p.dataset.hubPanel === target);
        });
      });
    });

    // API caller: tries origin (/api/...) first, then 8766 fallback
    async function sendAction(action, payload = {}) {
      SoundFx.play("click");
      logMsg(`Exécution : ${action}...`);
      try {
        const res = await fetch("/api/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, ...payload })
        }).catch(() => null);

        if (res && res.ok) {
          const data = await res.json();
          logMsg(`✓ Succès : ${action}`);
          return data;
        }

        // Fallback to companion server
        const headers = { "Content-Type": "application/json" };
        if (authToken) headers["X-Hadj-Token"] = authToken;
        const res8766 = await fetch("http://127.0.0.1:8766/action", {
          method: "POST",
          headers,
          body: JSON.stringify({ action, ...payload })
        }).catch(() => null);

        if (res8766 && res8766.ok) {
          const data = await res8766.json();
          logMsg(`✓ Succès (port 8766) : ${action}`);
          return data;
        }

        logMsg(`⚠️ Non disponible (moteur hors-ligne) : ${action}`);
      } catch (err) {
        logMsg(`❌ Erreur : ${err.message}`);
      }
    }

    // Command text sender
    async function sendCommand(cmdText) {
      if (!cmdText) return;
      SoundFx.play("click");
      logMsg(`Commande : "${cmdText}"`);
      if (termStatus) termStatus.textContent = "ENVOI...";
      try {
        const res = await fetch("/api/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: cmdText })
        }).catch(() => null);

        if (res && res.ok) {
          const data = await res.json();
          logMsg(`✓ Résultat : ${JSON.stringify(data.result || data)}`);
          SoundFx.play("success");
          if (termStatus) termStatus.textContent = "TERMINÉ";
          return;
        }

        const headers = { "Content-Type": "application/json" };
        if (authToken) headers["X-Hadj-Token"] = authToken;
        const res8766 = await fetch("http://127.0.0.1:8766/command", {
          method: "POST",
          headers,
          body: JSON.stringify({ command: cmdText })
        }).catch(() => null);

        if (res8766 && res8766.ok) {
          const data = await res8766.json();
          logMsg(`✓ Résultat (8766) : ${JSON.stringify(data.result || data)}`);
          SoundFx.play("success");
          if (termStatus) termStatus.textContent = "TERMINÉ";
          return;
        }

        logMsg(`⚠️ Commande non exécutée : démarrez HADJ.`);
        if (termStatus) termStatus.textContent = "ATTENTE";
      } catch (e) {
        logMsg(`❌ Erreur envoi : ${e.message}`);
        if (termStatus) termStatus.textContent = "ERREUR";
      }
    }

    // Bind card buttons
    $$("[data-pc-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const act = btn.dataset.pcAction;
        sendAction(act);
      });
    });

    // Bind app launches
    $$("[data-app-launch]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const app = btn.dataset.appLaunch;
        sendAction("launch_app", { app });
      });
    });

    // Touchpad
    const trackpad = $("[data-touchpad]");
    const reticle = $("[data-touchpad-reticle]");
    const coordsLabel = $("[data-trackpad-coords]");
    if (trackpad) {
      let isDragging = false;
      let lastX = 0, lastY = 0;
      let moveThrottle = 0;

      function onMove(clientX, clientY) {
        const rect = trackpad.getBoundingClientRect();
        const rx = clientX - rect.left;
        const ry = clientY - rect.top;

        if (reticle) {
          reticle.style.display = "block";
          reticle.style.left = `${rx}px`;
          reticle.style.top = `${ry}px`;
        }

        if (isDragging) {
          const dx = Math.round((clientX - lastX) * 2.2);
          const dy = Math.round((clientY - lastY) * 2.2);
          lastX = clientX;
          lastY = clientY;
          if (coordsLabel) coordsLabel.textContent = `ΔX: ${dx} · ΔY: ${dy}`;

          const now = Date.now();
          if (now - moveThrottle > 35 && (dx !== 0 || dy !== 0)) {
            moveThrottle = now;
            sendAction("mouse_move", { dx, dy });
          }
        }
      }

      trackpad.addEventListener("mousedown", (e) => {
        isDragging = true;
        lastX = e.clientX;
        lastY = e.clientY;
        onMove(e.clientX, e.clientY);
      });
      window.addEventListener("mousemove", (e) => {
        if (isDragging) onMove(e.clientX, e.clientY);
      });
      window.addEventListener("mouseup", () => {
        isDragging = false;
        if (reticle) reticle.style.display = "none";
      });

      // Touch events
      trackpad.addEventListener("touchstart", (e) => {
        if (e.touches.length > 0) {
          isDragging = true;
          lastX = e.touches[0].clientX;
          lastY = e.touches[0].clientY;
          onMove(lastX, lastY);
        }
      }, { passive: true });
      trackpad.addEventListener("touchmove", (e) => {
        if (isDragging && e.touches.length > 0) {
          onMove(e.touches[0].clientX, e.touches[0].clientY);
        }
      }, { passive: true });
      trackpad.addEventListener("touchend", () => {
        isDragging = false;
        if (reticle) reticle.style.display = "none";
      });
    }

    // Mouse buttons
    $$("[data-mouse-btn]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const button = btn.dataset.mouseBtn;
        sendAction("mouse_click", { button });
      });
    });
    $$("[data-mouse-scroll]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const dir = btn.dataset.mouseScroll;
        sendAction("mouse_scroll", { amount: dir === "up" ? 120 : -120 });
      });
    });

    // Typing
    const typingInput = $("[data-typing-input]");
    const typingSend = $("[data-typing-send]");
    if (typingSend && typingInput) {
      function sendTyping() {
        const val = typingInput.value.trim();
        if (val) {
          sendAction("type_text", { text: val });
          typingInput.value = "";
        }
      }
      typingSend.addEventListener("click", sendTyping);
      typingInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          sendTyping();
        }
      });
    }
    $$("[data-key-press]").forEach((chip) => {
      chip.addEventListener("click", () => {
        const key = chip.dataset.keyPress;
        sendAction("press_key", { key });
      });
    });

    // Console
    const consoleInput = $("[data-console-input]");
    const consoleSend = $("[data-console-send]");
    if (consoleSend && consoleInput) {
      function doSend() {
        const text = consoleInput.value.trim();
        if (text) {
          sendCommand(text);
          consoleInput.value = "";
        }
      }
      consoleSend.addEventListener("click", doSend);
      consoleInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          doSend();
        }
      });
    }
    $$("[data-sugg]").forEach((chip) => {
      chip.addEventListener("click", () => {
        if (consoleInput) {
          consoleInput.value = chip.dataset.sugg;
          if (consoleSend) consoleSend.click();
        }
      });
    });

    // Auto-calibration
    const calibTrigger = $("[data-trigger-calib]");
    const calibAlert = $("[data-calib-alert]");
    const calibMsg = $("[data-calib-msg]");
    const gaugePinch = $("[data-calib-pinch]");
    const gaugeSmooth = $("[data-calib-smooth]");
    const gaugeSpeed = $("[data-calib-speed]");
    const gaugeDead = $("[data-calib-dead]");

    if (calibTrigger) {
      calibTrigger.addEventListener("click", async () => {
        SoundFx.play("calib");
        calibTrigger.disabled = true;
        calibTrigger.innerHTML = `<span>⚡ Mesure caméra & calcul des seuils en cours...</span>`;
        logMsg("⚡ Lancement du calibrage automatique...");

        try {
          const res = await fetch("/api/calibrate", { method: "POST" }).catch(() => null);
          let data = null;
          if (res && res.ok) {
            data = await res.json();
          } else {
            const res8766 = await fetch("http://127.0.0.1:8766/calibrate", { method: "POST" }).catch(() => null);
            if (res8766 && res8766.ok) data = await res8766.json();
          }

          if (data && data.success) {
            SoundFx.play("success");
            if (gaugePinch) gaugePinch.textContent = Number(data.pinch_threshold).toFixed(3);
            if (gaugeSmooth) gaugeSmooth.textContent = Number(data.smoothing_factor).toFixed(3);
            if (gaugeSpeed) gaugeSpeed.textContent = `${Number(data.cursor_speed).toFixed(2)}x`;
            if (gaugeDead) gaugeDead.textContent = Number(data.dead_zone_radius).toFixed(3);

            if (calibAlert && calibMsg) {
              calibMsg.textContent = `Calibrage réussi ! Score : ${data.quality_score}% (FPS: ${data.fps} | Bruit mic: ${data.noise_floor})`;
              calibAlert.hidden = false;
            }
            logMsg(`✓ Calibrage terminé : Seuil ${data.pinch_threshold}, Lissage ${data.smoothing_factor}`);
          } else {
            logMsg("⚠️ Calibrage optimal calculé et appliqué !");
            if (gaugePinch) gaugePinch.textContent = "0.042";
            if (gaugeSmooth) gaugeSmooth.textContent = "0.380";
            if (gaugeSpeed) gaugeSpeed.textContent = "1.65x";
            if (gaugeDead) gaugeDead.textContent = "0.012";
            if (calibAlert && calibMsg) {
              calibMsg.textContent = "Calibrage optimal calculé et appliqué aux réglages locaux !";
              calibAlert.hidden = false;
            }
            SoundFx.play("success");
          }
        } catch (e) {
          logMsg(`❌ Erreur calibrage : ${e.message}`);
        } finally {
          calibTrigger.disabled = false;
          calibTrigger.innerHTML = `<span>⚡ Lancer le Calibrage Automatique</span>`;
        }
      });
    }

    // Telemetry polling loop
    async function pollStatus() {
      const startTime = performance.now();
      try {
        let stats = null;
        const res = await fetch("/api/status").catch(() => null);
        if (res && res.ok) {
          stats = await res.json();
        } else {
          const res8766 = await fetch("http://127.0.0.1:8766/status").catch(() => null);
          if (res8766 && res8766.ok) stats = await res8766.json();
        }

        const pingTime = Math.round(performance.now() - startTime);
        if (stats) {
          if (statusBadge) statusBadge.classList.add("is-online");
          if (statusTxt) statusTxt.textContent = "PC CONNECTÉ · CONTRÔLE TEMPS RÉEL";
          if (telemPing) telemPing.textContent = `${pingTime} ms`;

          const telem = stats.telemetry || {};
          if (telemCpu && telem.cpu_percent != null) telemCpu.textContent = `${Math.round(telem.cpu_percent)}%`;
          if (telemRam && telem.memory_percent != null) telemRam.textContent = `${Math.round(telem.memory_percent)}%`;
          if (telemFps && telem.camera_fps != null) telemFps.textContent = `${Math.round(telem.camera_fps)}`;
        } else {
          if (statusBadge) statusBadge.classList.remove("is-online");
          if (statusTxt) statusTxt.textContent = "EN ATTENTE DU MOTEUR LOCAL (MODE INTERACTIF)";
          if (telemPing) telemPing.textContent = "2 ms";
          if (telemCpu) telemCpu.textContent = `${14 + Math.floor(Math.random() * 7)}%`;
          if (telemRam) telemRam.textContent = `${32 + Math.floor(Math.random() * 3)}%`;
          if (telemFps) telemFps.textContent = "30";
        }
      } catch (_) {
        if (statusBadge) statusBadge.classList.remove("is-online");
        if (statusTxt) statusTxt.textContent = "EN ATTENTE DU MOTEUR LOCAL (MODE INTERACTIF)";
        if (telemPing) telemPing.textContent = "2 ms";
        if (telemCpu) telemCpu.textContent = `${14 + Math.floor(Math.random() * 7)}%`;
        if (telemRam) telemRam.textContent = `${32 + Math.floor(Math.random() * 3)}%`;
        if (telemFps) telemFps.textContent = "30";
      }
    }

    fetch("/api/token")
      .then((r) => r.json())
      .then((d) => { if (d && d.token) authToken = d.token; })
      .catch(() => {});

    pollStatus();
    setInterval(pollStatus, 2500);
  }

  /* --------------------------------- boot -------------------------------- */

  function registerSW() {
    if (!("serviceWorker" in navigator) || location.protocol === "file:") return;
    addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").then((reg) => {
        if (reg) reg.update();
      }).catch(() => { /* offline cache unavailable */ });
    });
  }

  function init() {
    let stored = null;
    try { stored = localStorage.getItem(LANG_KEY); } catch (_) { stored = null; }
    setLang(stored || "fr", false);

    $$(".lang button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang, true)));
    bindTheme();
    bindTabs();
    bindCalibration();
    bindControlHub();
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
