// Master translation interface — single source of truth.
// TypeScript will error if any language file is missing a key.

export interface Translation {
  appName: string;
  tagline: string;
  loading: string;
  error: string;
  save: string;
  cancel: string;
  close: string;
  confirm: string;
  delete: string;
  back: string;
  next: string;
  submit: string;
  tryAgain: string;
  learnMore: string;
  comingSoon: string;
  new: string;
  open: string;
  download: string;
  share: string;

  auth: {
    signIn: string;
    signUp: string;
    signOut: string;
    continueWithGoogle: string;
    sendMagicLink: string;
    magicLinkSent: string;
    magicLinkPrompt: string;
    emailPlaceholder: string;
    checkEmail: string;
    orContinueWith: string;
    alreadyHaveAccount: string;
    noAccount: string;
  };

  sidebar: {
    newChat: string;
    recentChats: string;
    myVideos: string;
    studySets: string;
    savedConcepts: string;
    progress: string;
    settings: string;
    today: string;
    yesterday: string;
    lastWeek: string;
    older: string;
    noConversations: string;
    searchConversations: string;
  };

  chat: {
    placeholder: string;
    placeholderWithFile: string;
    send: string;
    thinking: string;
    suggestions: string;
    makeItVisual: string;
    testYourself: string;
    goDeeper: string;
    simplify: string;
    giveExample: string;
    copyMessage: string;
    regenerate: string;
    stopGenerating: string;
    noMessages: string;
    welcomeTitle: string;
    welcomeSubtitle: string;
    starterPrompts: string[];
  };

  video: {
    generating: string;
    generatingDesc: string;
    ready: string;
    failed: string;
    failedDesc: string;
    saveToLibrary: string;
    savedToLibrary: string;
    duration: string;
    upgradeForLonger: string;
    myVideos: string;
    noVideos: string;
    noVideosDesc: string;
    comingSoonForSubject: string;
  };

  quiz: {
    title: string;
    startQuiz: string;
    nextQuestion: string;
    submitAnswer: string;
    seeResults: string;
    correct: string;
    incorrect: string;
    score: string;
    tryAgain: string;
    explanation: string;
    question: string;
    wellDone: string;
    keepPracticing: string;
  };

  upload: {
    dragDrop: string;
    orClick: string;
    uploading: string;
    analyzing: string;
    pdfLoaded: string;
    imageLoaded: string;
    selectPages: string;
    pageLimit: string;
    upgradeForMorePages: string;
    extractingConcepts: string;
    conceptsFound: string;
    selectRegion: string;
    askAboutSelection: string;
    unsupportedType: string;
    fileTooLarge: string;
  };

  studySets: {
    title: string;
    createNew: string;
    noSets: string;
    noSetsDesc: string;
    concepts: string;
    startStudying: string;
    masteryLevel: string;
    reviewDue: string;
    allMastered: string;
    flashcardMode: string;
    flip: string;
    knew: string;
    didntKnow: string;
    limitReached: string;
  };

  credits: {
    messagesLeft: string;
    videosLeft: string;
    dailyLimitReached: string;
    sessionLimitReached: string;
    upgradeToKeepLearning: string;
    saveProgress: string;
    saveProgressDesc: string;
    whatYouGet: string;
  };

  pricing: {
    free: string;
    learner: string;
    pro: string;
    month: string;
    year: string;
    saveWithAnnual: string;
    currentPlan: string;
    upgrade: string;
    cancelAnytime: string;
    features: {
      videoLength: string;
      messagesPerDay: string;
      pdfPages: string;
      studySets: string;
      quizzes: string;
      history: string;
      unlimited: string;
    };
  };

  settings: {
    title: string;
    language: string;
    knowledgeLevel: string;
    beginner: string;
    intermediate: string;
    advanced: string;
    theme: string;
    light: string;
    dark: string;
    system: string;
    account: string;
    billing: string;
    deleteAccount: string;
    deleteAccountConfirm: string;
  };

  errors: {
    generic: string;
    networkError: string;
    sessionExpired: string;
    uploadFailed: string;
    videoFailed: string;
    quotaExceeded: string;
    fileTooLarge: string;
    invalidFileType: string;
  };
}
