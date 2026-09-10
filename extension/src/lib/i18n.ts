import type { LanguageCode } from './api';

// Genie's own UI strings, in the same 6 languages as the web app. Keys
// marked "ported" below are copied verbatim from frontend/translations/
// (the exact same string the web app shows for the same action) so the two
// stay consistent. Keys marked "genie-only" don't exist in the app's
// translation files (they're UI genie alone has — the clip attachment
// chip, the selection-card prompts, etc.) and were hand-translated for
// this file rather than ported; if a native speaker wants to refine the
// wording, these are the ones to revisit first.
//
// Deliberately NOT translated, matching the web app's own behavior exactly
// (frontend/app/page.tsx and MessageBubble.tsx hardcode these in English
// regardless of the user's language too — not a genie-specific gap):
// "Can you simplify that explanation?", "Can you go deeper on that?",
// "Give me a concrete real-world example of this", "What is in this
// image?" (genie's equivalent: "What does this show? Please explain.").

export interface GenieStrings {
  // Header / global
  signIn: string; // ported
  signOut: string; // ported
  chatPlaceholder: string; // ported
  askAboutThisPlaceholder: string; // genie-only
  send: string; // genie-only
  uploading: string; // genie-only
  thinking: string; // genie-only
  welcomeHint: string; // genie-only

  // Action toolbar (per AI reply)
  quizMe: string; // ported
  walkMeThrough: string; // ported
  walkMeThroughPrompt: string; // ported — generic "walk me through that" (per-reply button)
  showExample: string; // ported (label only — prompt text stays English, see note above)
  simplify: string; // ported (label only)
  goDeeper: string; // ported (label only)
  animateIt: string; // ported (makeItVisual) — genie shows the button for toolbar parity with the app, but clicking it explains video generation lives in the full app instead of generating one here
  animateNotice: string; // genie-only — shown under the toolbar when Animate it is clicked
  goToLearnX: string; // genie-only — link label, used here and in the footer
  ttsReadAloud: string; // genie-only
  ttsGenerating: string; // genie-only
  ttsStop: string; // genie-only
  copy: string; // genie-only

  // Footer — persistent nudge back to the full app, every history-carrying
  // chat/quiz genie starts is a real conversation on the account/session,
  // so "continue there" is genuinely true, not just marketing copy.
  continueInLearnX: string; // genie-only

  // Selection card (from the "Ask LearnX" pill / context menu)
  cancelSelectionTitle: string; // genie-only
  justExplainIt: string; // genie-only
  explainThis: (text: string) => string; // genie-only
  walkMeThroughSelection: (text: string) => string; // genie-only — adapted from walkMeThroughPrompt to embed the selected text, since this is the FIRST message (no prior reply for "that" to refer to)
  quizMeOnThis: string; // genie-only

  // Quiz
  buildingQuiz: string; // genie-only — App.tsx's loading state, before the quiz exists
  quizInProgress: string; // genie-only — GenieQuiz's own collapsed-state label, once generated but not submitted
  quizSummary: (correct: number, total: number, pct: number) => string; // genie-only
  expand: string; // genie-only
  minimize: string; // genie-only
  submitAnswers: string; // genie-only
  submitting: string; // genie-only
  quizLimitMsg: string; // genie-only
  signInForMore: string; // genie-only
  quizSubmitError: string; // genie-only

  // Limits / errors
  limitReachedMsg: string; // genie-only
  signInToKeepGoing: string; // genie-only
  connectionError: string; // genie-only
  uploadError: string; // genie-only
  captureError: string; // genie-only

  // Screen clip
  clipButtonTitle: string; // genie-only
  clipAttached: string; // genie-only
  removeClip: string; // genie-only
  dragToSelect: string; // genie-only
  useThisRegion: string; // genie-only
  cancel: string; // genie-only

  // Sign-in form
  signInTitle: string; // genie-only
  createAccountTitle: string; // genie-only
  emailPlaceholder: string; // genie-only
  passwordPlaceholder: string; // genie-only
  passwordMinPlaceholder: string; // genie-only
  pleaseWait: string; // genie-only
  createAccount: string; // ported (createAccountBtn)
  noAccountPrompt: string; // ported (noAccount, reworded slightly to fit genie's flow)
  hasAccountPrompt: string; // ported (alreadyHaveAccount)
  authGenericError: string; // genie-only
  showPassword: string; // genie-only
  hidePassword: string; // genie-only
}

export const GENIE_TRANSLATIONS: Record<LanguageCode, GenieStrings> = {
  en: {
    signIn: 'Sign in',
    signOut: 'Sign out',
    chatPlaceholder: 'Ask a question…',
    askAboutThisPlaceholder: 'Ask about this (optional)…',
    send: 'Send',
    uploading: 'Uploading…',
    thinking: 'Thinking…',
    welcomeHint: 'Select some text on any page, then click "✨ Ask LearnX" (or right-click it) — or just type a question below.',
    quizMe: '✏️ Quiz me',
    walkMeThrough: '🧭 Walk me through it',
    walkMeThroughPrompt: 'Can you walk me through that one guiding question at a time, instead of just explaining it?',
    showExample: '💡 Show me an example',
    simplify: '↓ Simplify this',
    goDeeper: '↑ Go deeper',
    animateIt: '🎬 Animate it',
    animateNotice: 'Video generation is available in the full LearnX app.',
    goToLearnX: 'Go to learnx-ai.com',
    continueInLearnX: '💾 All chats saved — continue in LearnX →',
    ttsReadAloud: 'Read aloud',
    ttsGenerating: 'Generating audio…',
    ttsStop: 'Stop',
    copy: 'Copy',
    cancelSelectionTitle: 'Not the right text — cancel',
    justExplainIt: 'Just explain it',
    explainThis: (text) => `Explain this: "${text}"`,
    walkMeThroughSelection: (text) =>
      `Can you walk me through "${text}" one guiding question at a time, instead of just explaining it directly?`,
    quizMeOnThis: '🎯 Quiz me on this',
    buildingQuiz: 'Building your quiz…',
    quizInProgress: '🎯 Quiz (in progress)',
    quizSummary: (c, t, p) => `🎯 Quiz — ${c}/${t} (${Math.round(p)}%)`,
    expand: 'Expand ⌄',
    minimize: 'Minimize ⌃',
    submitAnswers: 'Submit answers',
    submitting: 'Submitting…',
    quizLimitMsg: "You've used your free quiz for this session.",
    signInForMore: 'Sign in for more',
    quizSubmitError: 'Could not submit the quiz',
    limitReachedMsg: "You've reached the free limit for this session.",
    signInToKeepGoing: 'Sign in to keep going',
    connectionError: "Couldn't reach LearnX. Check your connection and try again.",
    uploadError: "Couldn't upload the clipped image. Try again.",
    captureError: "Couldn't capture the page. Some pages (like chrome:// pages) can't be captured.",
    clipButtonTitle: 'Clip part of the screen to ask about',
    clipAttached: 'Clip attached — ask a question or just send',
    removeClip: 'Remove clipped image',
    dragToSelect: 'Drag to select the part you want to ask about.',
    useThisRegion: 'Use this region',
    cancel: 'Cancel',
    signInTitle: 'Sign in to LearnX',
    createAccountTitle: 'Create a LearnX account',
    emailPlaceholder: 'Email',
    passwordPlaceholder: 'Password',
    passwordMinPlaceholder: 'Password (min 8 characters)',
    pleaseWait: 'Please wait…',
    createAccount: 'Create account',
    noAccountPrompt: "Don't have an account? Create one",
    hasAccountPrompt: 'Already have an account? Sign in',
    authGenericError: 'Something went wrong',
    showPassword: 'Show password',
    hidePassword: 'Hide password',
  },
  fi: {
    signIn: 'Kirjaudu sisään',
    signOut: 'Kirjaudu ulos',
    chatPlaceholder: 'Esitä kysymys…',
    askAboutThisPlaceholder: 'Kysy tästä (valinnainen)…',
    send: 'Lähetä',
    uploading: 'Ladataan…',
    thinking: 'Mietitään…',
    welcomeHint: 'Valitse tekstiä millä tahansa sivulla ja klikkaa "✨ Ask LearnX" (tai oikea-klikkaa) — tai kirjoita kysymys alle.',
    quizMe: '✏️ Tentaa minua',
    walkMeThrough: '🧭 Opasta minua askel askeleelta',
    walkMeThroughPrompt: 'Voisitko opastaa minua yhdellä kysymyksellä kerrallaan sen selittämisen sijaan?',
    showExample: '💡 Näytä esimerkki',
    simplify: '↓ Yksinkertaista',
    goDeeper: '↑ Syvennä',
    animateIt: '🎬 Animoi se',
    animateNotice: 'Videoiden luonti on saatavilla LearnXin täydessä sovelluksessa.',
    goToLearnX: 'Siirry osoitteeseen learnx-ai.com',
    continueInLearnX: '💾 Kaikki keskustelut tallennettu — jatka LearnXissa →',
    ttsReadAloud: 'Lue ääneen',
    ttsGenerating: 'Luodaan ääntä…',
    ttsStop: 'Pysäytä',
    copy: 'Kopioi',
    cancelSelectionTitle: 'Väärä teksti — peruuta',
    justExplainIt: 'Vain selitä se',
    explainThis: (text) => `Selitä tämä: "${text}"`,
    walkMeThroughSelection: (text) =>
      `Voisitko opastaa minua kohdassa "${text}" yhdellä kysymyksellä kerrallaan sen suoraan selittämisen sijaan?`,
    quizMeOnThis: '🎯 Tentaa minua tästä',
    buildingQuiz: 'Luodaan tenttiäsi…',
    quizInProgress: '🎯 Tentti (kesken)',
    quizSummary: (c, t, p) => `🎯 Tentti — ${c}/${t} (${Math.round(p)}%)`,
    expand: 'Laajenna ⌄',
    minimize: 'Pienennä ⌃',
    submitAnswers: 'Lähetä vastaukset',
    submitting: 'Lähetetään…',
    quizLimitMsg: 'Olet käyttänyt tämän istunnon ilmaisen tentin.',
    signInForMore: 'Kirjaudu saadaksesi lisää',
    quizSubmitError: 'Tentin lähetys epäonnistui',
    limitReachedMsg: 'Olet saavuttanut tämän istunnon ilmaisen rajan.',
    signInToKeepGoing: 'Kirjaudu jatkaaksesi',
    connectionError: 'LearnXiin ei saatu yhteyttä. Tarkista yhteytesi ja yritä uudelleen.',
    uploadError: 'Leikatun kuvan lataus epäonnistui. Yritä uudelleen.',
    captureError: 'Sivun kaappaus epäonnistui. Joitain sivuja (kuten chrome://-sivuja) ei voi kaapata.',
    clipButtonTitle: 'Leikkaa osa näytöstä kysyäksesi siitä',
    clipAttached: 'Leike liitetty — kysy jotain tai lähetä suoraan',
    removeClip: 'Poista leikattu kuva',
    dragToSelect: 'Valitse vetämällä se osa, josta haluat kysyä.',
    useThisRegion: 'Käytä tätä aluetta',
    cancel: 'Peruuta',
    signInTitle: 'Kirjaudu LearnXiin',
    createAccountTitle: 'Luo LearnX-tili',
    emailPlaceholder: 'Sähköposti',
    passwordPlaceholder: 'Salasana',
    passwordMinPlaceholder: 'Salasana (vähintään 8 merkkiä)',
    pleaseWait: 'Hetki…',
    createAccount: 'Luo tili',
    noAccountPrompt: 'Ei tiliä? Luo ilmainen tili',
    hasAccountPrompt: 'Onko sinulla jo tili? Kirjaudu',
    authGenericError: 'Jotain meni pieleen',
    showPassword: 'Näytä salasana',
    hidePassword: 'Piilota salasana',
  },
  es: {
    signIn: 'Iniciar sesión',
    signOut: 'Cerrar sesión',
    chatPlaceholder: 'Haz una pregunta…',
    askAboutThisPlaceholder: 'Pregunta sobre esto (opcional)…',
    send: 'Enviar',
    uploading: 'Subiendo…',
    thinking: 'Pensando…',
    welcomeHint: 'Selecciona texto en cualquier página y haz clic en "✨ Ask LearnX" (o clic derecho) — o simplemente escribe una pregunta abajo.',
    quizMe: '✏️ Examíname',
    walkMeThrough: '🧭 Guíame paso a paso',
    walkMeThroughPrompt: '¿Puedes guiarme con una pregunta a la vez, en lugar de explicarlo directamente?',
    showExample: '💡 Muéstrame un ejemplo',
    simplify: '↓ Simplificar',
    goDeeper: '↑ Profundizar',
    animateIt: '🎬 Animarlo',
    animateNotice: 'La generación de vídeos está disponible en la aplicación completa de LearnX.',
    goToLearnX: 'Ir a learnx-ai.com',
    continueInLearnX: '💾 Todos los chats guardados — continúa en LearnX →',
    ttsReadAloud: 'Leer en voz alta',
    ttsGenerating: 'Generando audio…',
    ttsStop: 'Detener',
    copy: 'Copiar',
    cancelSelectionTitle: 'No es el texto correcto — cancelar',
    justExplainIt: 'Solo explícalo',
    explainThis: (text) => `Explica esto: "${text}"`,
    walkMeThroughSelection: (text) =>
      `¿Puedes guiarme por "${text}" con una pregunta a la vez, en lugar de explicarlo directamente?`,
    quizMeOnThis: '🎯 Examíname sobre esto',
    buildingQuiz: 'Creando tu cuestionario…',
    quizInProgress: '🎯 Cuestionario (en curso)',
    quizSummary: (c, t, p) => `🎯 Cuestionario — ${c}/${t} (${Math.round(p)}%)`,
    expand: 'Expandir ⌄',
    minimize: 'Minimizar ⌃',
    submitAnswers: 'Enviar respuestas',
    submitting: 'Enviando…',
    quizLimitMsg: 'Has usado tu cuestionario gratuito de esta sesión.',
    signInForMore: 'Inicia sesión para más',
    quizSubmitError: 'No se pudo enviar el cuestionario',
    limitReachedMsg: 'Has alcanzado el límite gratuito de esta sesión.',
    signInToKeepGoing: 'Inicia sesión para continuar',
    connectionError: 'No se pudo conectar con LearnX. Revisa tu conexión e inténtalo de nuevo.',
    uploadError: 'No se pudo subir la imagen recortada. Inténtalo de nuevo.',
    captureError: 'No se pudo capturar la página. Algunas páginas (como chrome://) no se pueden capturar.',
    clipButtonTitle: 'Recorta parte de la pantalla para preguntar sobre ella',
    clipAttached: 'Recorte adjunto — haz una pregunta o simplemente envía',
    removeClip: 'Quitar imagen recortada',
    dragToSelect: 'Arrastra para seleccionar la parte sobre la que quieres preguntar.',
    useThisRegion: 'Usar esta región',
    cancel: 'Cancelar',
    signInTitle: 'Inicia sesión en LearnX',
    createAccountTitle: 'Crea una cuenta de LearnX',
    emailPlaceholder: 'Correo electrónico',
    passwordPlaceholder: 'Contraseña',
    passwordMinPlaceholder: 'Contraseña (mínimo 8 caracteres)',
    pleaseWait: 'Un momento…',
    createAccount: 'Crear cuenta',
    noAccountPrompt: '¿No tienes cuenta? Regístrate gratis',
    hasAccountPrompt: '¿Ya tienes cuenta? Inicia sesión',
    authGenericError: 'Algo salió mal',
    showPassword: 'Mostrar contraseña',
    hidePassword: 'Ocultar contraseña',
  },
  fr: {
    signIn: 'Se connecter',
    signOut: 'Se déconnecter',
    chatPlaceholder: 'Posez une question…',
    askAboutThisPlaceholder: 'Poser une question à ce sujet (facultatif)…',
    send: 'Envoyer',
    uploading: 'Téléversement…',
    thinking: 'Réflexion…',
    welcomeHint: 'Sélectionnez du texte sur n\'importe quelle page, puis cliquez sur "✨ Ask LearnX" (ou clic droit) — ou tapez simplement une question ci-dessous.',
    quizMe: '✏️ Quiz',
    walkMeThrough: '🧭 Guide-moi étape par étape',
    walkMeThroughPrompt: "Peux-tu me guider une question à la fois, plutôt que de simplement l'expliquer ?",
    showExample: '💡 Montre-moi un exemple',
    simplify: '↓ Simplifier',
    goDeeper: '↑ Approfondir',
    animateIt: "🎬 L'animer",
    animateNotice: "La génération de vidéos est disponible dans l'application complète LearnX.",
    goToLearnX: 'Aller sur learnx-ai.com',
    continueInLearnX: '💾 Toutes les discussions sont enregistrées — continuer sur LearnX →',
    ttsReadAloud: 'Lire à voix haute',
    ttsGenerating: 'Génération audio…',
    ttsStop: 'Arrêter',
    copy: 'Copier',
    cancelSelectionTitle: "Ce n'est pas le bon texte — annuler",
    justExplainIt: 'Explique simplement',
    explainThis: (text) => `Explique ceci : "${text}"`,
    walkMeThroughSelection: (text) =>
      `Peux-tu me guider sur "${text}" une question à la fois, plutôt que de l'expliquer directement ?`,
    quizMeOnThis: '🎯 Quiz sur ceci',
    buildingQuiz: 'Création de ton quiz…',
    quizInProgress: '🎯 Quiz (en cours)',
    quizSummary: (c, t, p) => `🎯 Quiz — ${c}/${t} (${Math.round(p)}%)`,
    expand: 'Agrandir ⌄',
    minimize: 'Réduire ⌃',
    submitAnswers: 'Envoyer les réponses',
    submitting: 'Envoi…',
    quizLimitMsg: 'Vous avez utilisé votre quiz gratuit pour cette session.',
    signInForMore: 'Connectez-vous pour plus',
    quizSubmitError: "Impossible d'envoyer le quiz",
    limitReachedMsg: 'Vous avez atteint la limite gratuite de cette session.',
    signInToKeepGoing: 'Connectez-vous pour continuer',
    connectionError: "Impossible de joindre LearnX. Vérifiez votre connexion et réessayez.",
    uploadError: "Impossible d'envoyer l'image découpée. Réessayez.",
    captureError: "Impossible de capturer la page. Certaines pages (comme chrome://) ne peuvent pas être capturées.",
    clipButtonTitle: "Découper une partie de l'écran pour poser une question",
    clipAttached: 'Découpage joint — posez une question ou envoyez directement',
    removeClip: 'Retirer l\'image découpée',
    dragToSelect: 'Faites glisser pour sélectionner la partie sur laquelle vous voulez une question.',
    useThisRegion: 'Utiliser cette zone',
    cancel: 'Annuler',
    signInTitle: 'Se connecter à LearnX',
    createAccountTitle: 'Créer un compte LearnX',
    emailPlaceholder: 'E-mail',
    passwordPlaceholder: 'Mot de passe',
    passwordMinPlaceholder: 'Mot de passe (8 caractères min.)',
    pleaseWait: 'Un instant…',
    createAccount: 'Créer un compte',
    noAccountPrompt: "Pas encore de compte ? S'inscrire gratuitement",
    hasAccountPrompt: 'Déjà un compte ? Se connecter',
    authGenericError: "Une erreur s'est produite",
    showPassword: 'Afficher le mot de passe',
    hidePassword: 'Masquer le mot de passe',
  },
  no: {
    signIn: 'Logg inn',
    signOut: 'Logg ut',
    chatPlaceholder: 'Still et spørsmål…',
    askAboutThisPlaceholder: 'Spør om dette (valgfritt)…',
    send: 'Send',
    uploading: 'Laster opp…',
    thinking: 'Tenker…',
    welcomeHint: 'Merk tekst på en hvilken som helst side, og klikk "✨ Ask LearnX" (eller høyreklikk) — eller skriv et spørsmål under.',
    quizMe: '✏️ Test meg',
    walkMeThrough: '🧭 Vis meg steg for steg',
    walkMeThroughPrompt: 'Kan du veilede meg med ett spørsmål om gangen, i stedet for å bare forklare det?',
    showExample: '💡 Vis meg et eksempel',
    simplify: '↓ Forenkle dette',
    goDeeper: '↑ Gå dypere',
    animateIt: '🎬 Animer det',
    animateNotice: 'Videogenerering er tilgjengelig i den fullstendige LearnX-appen.',
    goToLearnX: 'Gå til learnx-ai.com',
    continueInLearnX: '💾 Alle samtaler lagret — fortsett i LearnX →',
    ttsReadAloud: 'Les høyt',
    ttsGenerating: 'Genererer lyd…',
    ttsStop: 'Stopp',
    copy: 'Kopier',
    cancelSelectionTitle: 'Feil tekst — avbryt',
    justExplainIt: 'Bare forklar det',
    explainThis: (text) => `Forklar dette: "${text}"`,
    walkMeThroughSelection: (text) =>
      `Kan du veilede meg gjennom "${text}" med ett spørsmål om gangen, i stedet for å forklare det direkte?`,
    quizMeOnThis: '🎯 Test meg på dette',
    buildingQuiz: 'Bygger quizen din…',
    quizInProgress: '🎯 Quiz (pågår)',
    quizSummary: (c, t, p) => `🎯 Quiz — ${c}/${t} (${Math.round(p)}%)`,
    expand: 'Utvid ⌄',
    minimize: 'Minimer ⌃',
    submitAnswers: 'Send svar',
    submitting: 'Sender…',
    quizLimitMsg: 'Du har brukt din gratis quiz for denne økten.',
    signInForMore: 'Logg inn for mer',
    quizSubmitError: 'Kunne ikke sende inn quizen',
    limitReachedMsg: 'Du har nådd den gratis grensen for denne økten.',
    signInToKeepGoing: 'Logg inn for å fortsette',
    connectionError: 'Fikk ikke kontakt med LearnX. Sjekk tilkoblingen og prøv igjen.',
    uploadError: 'Kunne ikke laste opp det klipte bildet. Prøv igjen.',
    captureError: 'Kunne ikke fange siden. Enkelte sider (som chrome://) kan ikke fanges.',
    clipButtonTitle: 'Klipp ut en del av skjermen å spørre om',
    clipAttached: 'Utklipp lagt ved — still et spørsmål eller bare send',
    removeClip: 'Fjern det klipte bildet',
    dragToSelect: 'Dra for å velge delen du vil spørre om.',
    useThisRegion: 'Bruk dette området',
    cancel: 'Avbryt',
    signInTitle: 'Logg inn på LearnX',
    createAccountTitle: 'Opprett en LearnX-konto',
    emailPlaceholder: 'E-post',
    passwordPlaceholder: 'Passord',
    passwordMinPlaceholder: 'Passord (minst 8 tegn)',
    pleaseWait: 'Et øyeblikk…',
    createAccount: 'Opprett konto',
    noAccountPrompt: 'Har du ikke en konto? Registrer deg gratis',
    hasAccountPrompt: 'Har du allerede en konto? Logg inn',
    authGenericError: 'Noe gikk galt',
    showPassword: 'Vis passord',
    hidePassword: 'Skjul passord',
  },
  sv: {
    signIn: 'Logga in',
    signOut: 'Logga ut',
    chatPlaceholder: 'Ställ en fråga…',
    askAboutThisPlaceholder: 'Fråga om detta (valfritt)…',
    send: 'Skicka',
    uploading: 'Laddar upp…',
    thinking: 'Tänker…',
    welcomeHint: 'Markera text på vilken sida som helst och klicka på "✨ Ask LearnX" (eller högerklicka) — eller skriv en fråga nedan.',
    quizMe: '✏️ Testa mig',
    walkMeThrough: '🧭 Vägled mig steg för steg',
    walkMeThroughPrompt: 'Kan du vägleda mig med en fråga i taget, istället för att bara förklara det?',
    showExample: '💡 Visa mig ett exempel',
    simplify: '↓ Förenkla detta',
    goDeeper: '↑ Fördjupa',
    animateIt: '🎬 Animera det',
    animateNotice: 'Videogenerering är tillgänglig i den fullständiga LearnX-appen.',
    goToLearnX: 'Gå till learnx-ai.com',
    continueInLearnX: '💾 Alla chattar sparade — fortsätt i LearnX →',
    ttsReadAloud: 'Läs upp',
    ttsGenerating: 'Genererar ljud…',
    ttsStop: 'Stoppa',
    copy: 'Kopiera',
    cancelSelectionTitle: 'Fel text — avbryt',
    justExplainIt: 'Förklara bara',
    explainThis: (text) => `Förklara detta: "${text}"`,
    walkMeThroughSelection: (text) =>
      `Kan du vägleda mig genom "${text}" med en fråga i taget, istället för att förklara det direkt?`,
    quizMeOnThis: '🎯 Testa mig på detta',
    buildingQuiz: 'Skapar ditt quiz…',
    quizInProgress: '🎯 Quiz (pågår)',
    quizSummary: (c, t, p) => `🎯 Quiz — ${c}/${t} (${Math.round(p)}%)`,
    expand: 'Expandera ⌄',
    minimize: 'Minimera ⌃',
    submitAnswers: 'Skicka svar',
    submitting: 'Skickar…',
    quizLimitMsg: 'Du har använt ditt gratis quiz för den här sessionen.',
    signInForMore: 'Logga in för mer',
    quizSubmitError: 'Kunde inte skicka in quizet',
    limitReachedMsg: 'Du har nått den gratis gränsen för den här sessionen.',
    signInToKeepGoing: 'Logga in för att fortsätta',
    connectionError: 'Kunde inte nå LearnX. Kontrollera din anslutning och försök igen.',
    uploadError: 'Kunde inte ladda upp den klippta bilden. Försök igen.',
    captureError: 'Kunde inte fånga sidan. Vissa sidor (som chrome://) kan inte fångas.',
    clipButtonTitle: 'Klipp ut en del av skärmen att fråga om',
    clipAttached: 'Klipp bifogat — ställ en fråga eller skicka direkt',
    removeClip: 'Ta bort den klippta bilden',
    dragToSelect: 'Dra för att markera delen du vill fråga om.',
    useThisRegion: 'Använd detta område',
    cancel: 'Avbryt',
    signInTitle: 'Logga in på LearnX',
    createAccountTitle: 'Skapa ett LearnX-konto',
    emailPlaceholder: 'E-post',
    passwordPlaceholder: 'Lösenord',
    passwordMinPlaceholder: 'Lösenord (minst 8 tecken)',
    pleaseWait: 'Ett ögonblick…',
    createAccount: 'Skapa konto',
    noAccountPrompt: 'Inget konto? Skapa ett gratis konto',
    hasAccountPrompt: 'Har du redan ett konto? Logga in',
    authGenericError: 'Något gick fel',
    showPassword: 'Visa lösenord',
    hidePassword: 'Dölj lösenord',
  },
};
