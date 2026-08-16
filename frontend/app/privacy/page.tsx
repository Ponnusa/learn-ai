'use client';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { useLanguageStore } from '@/store/languageStore';

type Row = [string, string];
type Block =
  | { type: 'p'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'table'; rows: Row[] };
type Section = { num: string; title: string; blocks: Block[] };
type Content = { title: string; lastUpdated: string; sections: Section[] };

const CONTENT: Record<string, Content> = {
  en: {
    title: 'Privacy Policy',
    lastUpdated: 'Last updated: 15 April 2026',
    sections: [
      { num: '1', title: 'Data Controller', blocks: [
        { type: 'p', text: 'The data controller for LearnX-AI is:' },
        { type: 'table', rows: [['Company', 'NordX Labs Oy'], ['Business ID (Y-tunnus)', '3615236-4'], ['Email', 'hello@animlearn.com']] },
      ]},
      { num: '2', title: 'What Data We Collect', blocks: [
        { type: 'table', rows: [
          ['Account', 'Full name, email address, preferred language, account creation date'],
          ['Google Sign-In (optional)', 'Google user ID, profile picture URL, name and email from Google OAuth'],
          ['Learning activity', 'Video watch percentage, concept mastery scores, practice attempts and answers, AI feedback on submissions, time taken on exercises'],
          ['Chat history', 'Problem-solving conversations with the AI tutor'],
          ['Security logs', 'IP address, browser user-agent — recorded on sign-in/sign-up for fraud prevention. Retained for 90 days, then deleted automatically.'],
        ]},
      ]},
      { num: '3', title: 'Legal Basis for Processing', blocks: [
        { type: 'p', text: 'Processing of personal data in LearnX-AI is based on public interest and the exercise of official authority (GDPR Article 6(1)(e)), in connection with the school\'s educational activities.' },
        { type: 'p', text: 'Security logging (IP address, user-agent) is based on our legitimate interest (Article 6(1)(f)) in preventing unauthorised access and fraud.' },
      ]},
      { num: '4', title: 'Profiling and Automated Processing', blocks: [
        { type: 'p', text: 'LearnX-AI automatically analyses your learning activity to personalise the educational experience. This includes:' },
        { type: 'ul', items: [
          'Calculating a mastery score (0–1) per concept based on your quiz answers and practice attempts',
          'Tracking a learning trend (improving / stable / declining) per concept',
          'Monitoring video watch completion to identify gaps in learning',
          'Generating personalised practice questions based on your performance',
        ]},
        { type: 'p', text: 'This constitutes profiling under GDPR Article 4(4). The profiling is carried out in the public interest as part of educational activities. It does not produce legal effects or significantly affect you.' },
      ]},
      { num: '5', title: 'Third-Party Processors', blocks: [
        { type: 'p', text: 'We share data with the following third-party service providers acting as data processors:' },
        { type: 'table', rows: [
          ['Google LLC', 'Google OAuth authentication. Data transferred: name, email, Google user ID. Governed by Google\'s Data Processing Terms.'],
          ['Anthropic / Claude (via Google Cloud Vertex AI, EU)', 'AI content generation. Hosted on Google Cloud within the EU. No student personal identifiers are sent to the model.'],
          ['Microsoft Azure (EU)', 'AI embeddings for syllabus search (Azure OpenAI). Document text processed in EU region.'],
          ['Cloudflare R2 (EU)', 'Storage of generated video files and SVG assets.'],
          ['Supabase / PostgreSQL', 'Database hosting for all user and learning data.'],
        ]},
        { type: 'p', text: 'We do not sell personal data to any third party.' },
      ]},
      { num: '6', title: 'Data Retention', blocks: [
        { type: 'table', rows: [
          ['Account data', 'Retained while your account is active. Deleted on account deletion request.'],
          ['Learning activity', 'Retained while your account is active. Deleted on account deletion.'],
          ['Security logs (IP, user-agent)', 'Automatically deleted after 90 days.'],
          ['AI-generated videos', 'Retained while linked to your account. Deleted on account deletion.'],
        ]},
      ]},
      { num: '7', title: 'Your Rights', blocks: [
        { type: 'p', text: 'Under GDPR, you have the following rights:' },
        { type: 'ul', items: [
          'Right of access — request a copy of your personal data',
          'Right to rectification — correct inaccurate data via Settings',
          'Right to erasure — delete your account and all associated data via Settings → Delete Account',
          'Right to restriction — request that we limit processing of your data',
          'Right to object — object to processing based on public interest',
          'Right to data portability — request your data in a machine-readable format',
        ]},
        { type: 'p', text: 'To exercise any of these rights, contact us at hello@animlearn.com. We will respond within 30 days.' },
        { type: 'p', text: 'You also have the right to lodge a complaint with the Finnish Data Protection Ombudsman (tietosuoja.fi).' },
      ]},
      { num: '8', title: 'Data Security', blocks: [
        { type: 'ul', items: [
          'Passwords are hashed using bcrypt (never stored in plaintext)',
          'All data in transit is encrypted with TLS/HTTPS',
          'Authentication tokens are stored locally in the browser and not sent to third parties',
          'Access to production databases is restricted to authorised personnel',
        ]},
      ]},
      { num: '9', title: 'Cookies and Local Storage', blocks: [
        { type: 'p', text: 'LearnX-AI does not use tracking cookies. Authentication tokens are stored in your browser\'s localStorage and are used only to keep you logged in. No third-party analytics or advertising cookies are used.' },
      ]},
      { num: '10', title: "Children's Data", blocks: [
        { type: 'p', text: 'LearnX-AI is designed for use in schools, including by minors. Student accounts are created and managed within the school context. Teachers and school administrators are responsible for ensuring that student accounts comply with applicable laws on processing children\'s data.' },
        { type: 'p', text: 'We do not knowingly collect data from children outside of a supervised educational context.' },
      ]},
      { num: '11', title: 'Changes to This Policy', blocks: [
        { type: 'p', text: 'We may update this privacy policy from time to time. When we do, we will update the "Last updated" date at the top of this page. Material changes will be communicated via the application or by email.' },
      ]},
      { num: '12', title: 'Contact', blocks: [
        { type: 'table', rows: [['Company', 'NordX Labs Oy'], ['Email', 'hello@animlearn.com']] },
      ]},
    ],
  },

  fi: {
    title: 'Tietosuojaseloste',
    lastUpdated: 'Viimeksi päivitetty: 15. huhtikuuta 2026',
    sections: [
      { num: '1', title: 'Rekisterinpitäjä', blocks: [
        { type: 'p', text: 'LearnX-AI:n rekisterinpitäjä on:' },
        { type: 'table', rows: [['Yritys', 'NordX Labs Oy'], ['Y-tunnus', '3615236-4'], ['Sähköposti', 'hello@animlearn.com']] },
      ]},
      { num: '2', title: 'Mitä tietoja keräämme', blocks: [
        { type: 'table', rows: [
          ['Tilitiedot', 'Koko nimi, sähköpostiosoite, kieliasetukset, tilin luontipäivämäärä'],
          ['Google-kirjautuminen (valinnainen)', 'Google-käyttäjätunnus, profiilikuvan URL, nimi ja sähköposti Google OAuth:sta'],
          ['Oppimistoiminta', 'Videoiden katseluprosentti, hallintapisteet, harjoitustehtävien yritykset ja vastaukset, tekoälypalaute, tehtäviin käytetty aika'],
          ['Keskusteluhistoria', 'Ongelmanratkaisukeskustelut tekoälytutorin kanssa'],
          ['Turvallisuuslokit', 'IP-osoite, selaimen käyttäjätunniste — tallennetaan kirjautumisen yhteydessä petostenestoon. Säilytetään 90 päivää, poistetaan automaattisesti.'],
        ]},
      ]},
      { num: '3', title: 'Käsittelyn oikeusperusta', blocks: [
        { type: 'p', text: 'LearnX-AI:n henkilötietojen käsittely perustuu yleistä etua koskevaan tehtävään ja julkisen vallan käyttöön (GDPR 6 artiklan 1 kohdan e alakohta) koulujen oppimistoiminnan yhteydessä.' },
        { type: 'p', text: 'Turvallisuuslokien käsittely perustuu oikeutettuun etuumme (6 artiklan 1 kohdan f alakohta) luvattoman käytön ja petosteneston estämiseksi.' },
      ]},
      { num: '4', title: 'Profilointi ja automaattinen käsittely', blocks: [
        { type: 'p', text: 'LearnX-AI analysoi automaattisesti oppimistoimintaasi personoidakseen oppimiskokemustasi. Tähän sisältyy:' },
        { type: 'ul', items: [
          'Hallintapisteen (0–1) laskeminen käsitettä kohden tenttivastauksiesi ja harjoitusyritystesi perusteella',
          'Oppimistrendin (paraneva / vakaa / heikkenevä) seuranta käsitettä kohden',
          'Videoiden katseluasteen seuranta oppimisaukkojen tunnistamiseksi',
          'Henkilökohtaisten harjoitustehtävien luominen suorituksesi perusteella',
        ]},
        { type: 'p', text: 'Tämä on GDPR:n 4 artiklan 4 kohdassa tarkoitettua profilointia. Profilointi tehdään yleistä etua koskevana tehtävänä osana oppimistoimintaa. Sillä ei ole oikeudellisia vaikutuksia eikä se vaikuta sinuun merkittävästi.' },
      ]},
      { num: '5', title: 'Kolmansien osapuolten käsittelijät', blocks: [
        { type: 'p', text: 'Jaamme tietoja seuraavien kolmansien osapuolten palveluntarjoajien kanssa:' },
        { type: 'table', rows: [
          ['Google LLC', 'Google OAuth -todennus. Siirrettävät tiedot: nimi, sähköposti, Google-käyttäjätunnus.'],
          ['Anthropic / Claude (Google Cloud Vertex AI, EU)', 'Tekoälysisällön tuottaminen. Google Cloud EU -infrastruktuurissa. Oppilaiden henkilötunnisteita ei lähetetä mallille.'],
          ['Microsoft Azure (EU)', 'Tekoälypohjaiset upotukset opetussuunnitelman hakuun. EU:n alueella.'],
          ['Cloudflare R2 (EU)', 'Luotujen videotiedostojen ja SVG-resurssien tallennus.'],
          ['Supabase / PostgreSQL', 'Kaikkien käyttäjä- ja oppimistietojen tietokannan isännöinti.'],
        ]},
        { type: 'p', text: 'Emme myy henkilötietoja kolmansille osapuolille.' },
      ]},
      { num: '6', title: 'Tietojen säilytysajat', blocks: [
        { type: 'table', rows: [
          ['Tilitiedot', 'Säilytetään, kun tili on aktiivinen. Poistetaan tilin poistohetkellä.'],
          ['Oppimistoiminta', 'Säilytetään, kun tili on aktiivinen. Poistetaan tilin poistohetkellä.'],
          ['Turvallisuuslokit (IP, käyttäjätunniste)', 'Poistetaan automaattisesti 90 päivän kuluttua.'],
          ['Tekoälyn luomat videot', 'Säilytetään, kun ne on linkitetty tilillesi. Poistetaan tilin poistohetkellä.'],
        ]},
      ]},
      { num: '7', title: 'Oikeutesi', blocks: [
        { type: 'p', text: 'GDPR:n nojalla sinulla on seuraavat oikeudet:' },
        { type: 'ul', items: [
          'Oikeus saada tietoja — pyydä kopio henkilötiedoistasi',
          'Oikeus tietojen oikaisemiseen — korjaa virheelliset tiedot Asetuksissa',
          'Oikeus tietojen poistamiseen — poista tilisi ja kaikki siihen liittyvät tiedot Asetukset → Poista tili -toiminnon kautta',
          'Oikeus käsittelyn rajoittamiseen — pyydä meitä rajoittamaan tietojesi käsittelyä',
          'Oikeus vastustaa — vastusta yleistä etua koskevaan tehtävään perustuvaa käsittelyä',
          'Oikeus siirtää tiedot järjestelmästä toiseen — pyydä tietosi koneluettavassa muodossa',
        ]},
        { type: 'p', text: 'Näiden oikeuksien käyttämiseksi ota yhteyttä osoitteeseen hello@animlearn.com. Vastaamme 30 päivän kuluessa.' },
        { type: 'p', text: 'Sinulla on myös oikeus tehdä valitus tietosuojavaltuutetulle (tietosuoja.fi).' },
      ]},
      { num: '8', title: 'Tietoturva', blocks: [
        { type: 'ul', items: [
          'Salasanat hajautetaan bcrypt-algoritmilla (ei koskaan selkokielisiä)',
          'Kaikki siirrettävä data salataan TLS/HTTPS-yhteydellä',
          'Todennustunnukset tallennetaan paikallisesti selaimeen eikä niitä lähetetä kolmansille osapuolille',
          'Pääsy tuotantotietokantoihin on rajattu valtuutetulle henkilökunnalle',
        ]},
      ]},
      { num: '9', title: 'Evästeet ja paikallinen tallennustila', blocks: [
        { type: 'p', text: 'LearnX-AI ei käytä seurantaevästeitä. Todennustunnukset tallennetaan selaimen paikalliseen tallennustilaan ja niitä käytetään ainoastaan kirjautuneena pysymiseen. Kolmansien osapuolten analytiikka- tai mainosevästeitä ei käytetä.' },
      ]},
      { num: '10', title: 'Alaikäisten tiedot', blocks: [
        { type: 'p', text: 'LearnX-AI on suunniteltu kouluissa käytettäväksi, myös alaikäisten toimesta. Opiskelijatilit luodaan ja hallitaan koulun puitteissa. Opettajat ja koulun ylläpitäjät vastaavat siitä, että opiskelijatilit noudattavat lasten henkilötietojen käsittelyä koskevia sovellettavia lakeja.' },
        { type: 'p', text: 'Emme tietoisesti kerää tietoja alaikäisiltä valvotun oppimisympäristön ulkopuolella.' },
      ]},
      { num: '11', title: 'Muutokset tietosuojaselosteeseen', blocks: [
        { type: 'p', text: 'Voimme päivittää tätä tietosuojaselostetta ajoittain. Teemme sen päivittämällä sivun yläosassa olevan päivämäärän. Olennaisista muutoksista tiedotetaan sovelluksen kautta tai sähköpostitse.' },
      ]},
      { num: '12', title: 'Yhteystiedot', blocks: [
        { type: 'table', rows: [['Yritys', 'NordX Labs Oy'], ['Sähköposti', 'hello@animlearn.com']] },
      ]},
    ],
  },

  sv: {
    title: 'Integritetspolicy',
    lastUpdated: 'Senast uppdaterad: 15 april 2026',
    sections: [
      { num: '1', title: 'Personuppgiftsansvarig', blocks: [
        { type: 'p', text: 'Den personuppgiftsansvarige för LearnX-AI är:' },
        { type: 'table', rows: [['Företag', 'NordX Labs Oy'], ['Företags-ID (Y-tunnus)', '3615236-4'], ['E-post', 'hello@animlearn.com']] },
      ]},
      { num: '2', title: 'Vilka uppgifter vi samlar in', blocks: [
        { type: 'table', rows: [
          ['Konto', 'Fullständigt namn, e-postadress, föredraget språk, datum för kontoskapande'],
          ['Google-inloggning (valfritt)', 'Google-användar-ID, profilbildens URL, namn och e-post från Google OAuth'],
          ['Lärande aktivitet', 'Procentandel av videovisning, behärskandepoäng, övningsförsök och svar, AI-feedback, tidsåtgång'],
          ['Chatthistorik', 'Problemlösningssamtal med AI-handledaren'],
          ['Säkerhetsloggar', 'IP-adress, webbläsarens user-agent — registreras vid inloggning för att förhindra bedrägeri. Sparas 90 dagar.'],
        ]},
      ]},
      { num: '3', title: 'Rättslig grund för behandling', blocks: [
        { type: 'p', text: 'Behandlingen av personuppgifter i LearnX-AI baseras på allmänt intresse och myndighetsutövning (GDPR Artikel 6(1)(e)), i samband med skolans utbildningsverksamhet.' },
        { type: 'p', text: 'Säkerhetsloggning baseras på vårt berättigade intresse (Artikel 6(1)(f)) att förhindra obehörig åtkomst och bedrägeri.' },
      ]},
      { num: '4', title: 'Profilering och automatiserad behandling', blocks: [
        { type: 'p', text: 'LearnX-AI analyserar automatiskt din inlärningsaktivitet för att personalisera utbildningsupplevelsen. Detta inkluderar:' },
        { type: 'ul', items: [
          'Beräkning av behärskandepoäng (0–1) per begrepp baserat på dina quiz-svar och övningsförsök',
          'Spårning av inlärningstrend (förbättrande / stabil / försämrande) per begrepp',
          'Övervakning av videovisningsgrad för att identifiera inlärningsluckor',
          'Generering av personliga övningsfrågor baserat på din prestation',
        ]},
        { type: 'p', text: 'Detta utgör profilering enligt GDPR Artikel 4(4). Profileringen utförs i allmänhetens intresse som en del av utbildningsverksamheten.' },
      ]},
      { num: '5', title: 'Tredjepartsbehandlare', blocks: [
        { type: 'table', rows: [
          ['Google LLC', 'Google OAuth-autentisering. Namn, e-post, Google-användar-ID.'],
          ['Anthropic / Claude (via Google Cloud Vertex AI, EU)', 'AI-innehållsgenerering. Hosted på Google Cloud inom EU. Inga elevers personliga identifierare skickas till modellen.'],
          ['Microsoft Azure (EU)', 'AI-inbäddningar för kursplansökning. Dokumenttext behandlas i EU-region.'],
          ['Cloudflare R2 (EU)', 'Lagring av genererade videofiler och SVG-resurser.'],
          ['Supabase / PostgreSQL', 'Databashosting för alla användar- och inlärningsdata.'],
        ]},
        { type: 'p', text: 'Vi säljer inte personuppgifter till tredje part.' },
      ]},
      { num: '6', title: 'Datalagring', blocks: [
        { type: 'table', rows: [
          ['Kontodata', 'Lagras medan ditt konto är aktivt. Raderas vid kontoborttagning.'],
          ['Inlärningsaktivitet', 'Lagras medan ditt konto är aktivt. Raderas vid kontoborttagning.'],
          ['Säkerhetsloggar (IP, user-agent)', 'Raderas automatiskt efter 90 dagar.'],
          ['AI-genererade videor', 'Lagras medan de är kopplade till ditt konto. Raderas vid kontoborttagning.'],
        ]},
      ]},
      { num: '7', title: 'Dina rättigheter', blocks: [
        { type: 'p', text: 'Enligt GDPR har du följande rättigheter:' },
        { type: 'ul', items: [
          'Rätt till tillgång — begär en kopia av dina personuppgifter',
          'Rätt till rättelse — korrigera felaktiga uppgifter via Inställningar',
          'Rätt till radering — radera ditt konto och all tillhörande data via Inställningar → Radera konto',
          'Rätt till begränsning — begär att vi begränsar behandlingen av dina uppgifter',
          'Rätt att invända — invända mot behandling baserad på allmänt intresse',
          'Rätt till dataportabilitet — begär dina uppgifter i maskinläsbart format',
        ]},
        { type: 'p', text: 'Kontakta oss på hello@animlearn.com för att utöva dina rättigheter. Vi svarar inom 30 dagar.' },
        { type: 'p', text: 'Du har också rätt att lämna in ett klagomål till det finska dataskyddsombudet (tietosuoja.fi).' },
      ]},
      { num: '8', title: 'Datasäkerhet', blocks: [
        { type: 'ul', items: [
          'Lösenord hashas med bcrypt (lagras aldrig i klartext)',
          'All data i transit krypteras med TLS/HTTPS',
          'Autentiseringstokens lagras lokalt i webbläsaren och skickas inte till tredje part',
          'Åtkomst till produktionsdatabaser är begränsad till behörig personal',
        ]},
      ]},
      { num: '9', title: 'Cookies och lokal lagring', blocks: [
        { type: 'p', text: 'LearnX-AI använder inga spårningscookies. Autentiseringstokens lagras i webbläsarens localStorage och används endast för att hålla dig inloggad. Inga tredjepartsanalytics- eller reklamcookies används.' },
      ]},
      { num: '10', title: 'Barns uppgifter', blocks: [
        { type: 'p', text: 'LearnX-AI är utformat för användning i skolor, inklusive av minderåriga. Elevkonton skapas och hanteras inom skolkontexten. Lärare och skoladministratörer ansvarar för att elevkonton följer tillämpliga lagar om behandling av barns uppgifter.' },
        { type: 'p', text: 'Vi samlar inte medvetet in uppgifter från barn utanför en övervakad utbildningskontext.' },
      ]},
      { num: '11', title: 'Ändringar i denna policy', blocks: [
        { type: 'p', text: 'Vi kan uppdatera denna integritetspolicy från tid till annan. När vi gör det uppdaterar vi datumet "Senast uppdaterad" högst upp på sidan. Väsentliga ändringar kommuniceras via applikationen eller via e-post.' },
      ]},
      { num: '12', title: 'Kontakt', blocks: [
        { type: 'table', rows: [['Företag', 'NordX Labs Oy'], ['E-post', 'hello@animlearn.com']] },
      ]},
    ],
  },

  fr: {
    title: 'Politique de confidentialité',
    lastUpdated: 'Dernière mise à jour : 15 avril 2026',
    sections: [
      { num: '1', title: 'Responsable du traitement', blocks: [
        { type: 'p', text: 'Le responsable du traitement pour LearnX-AI est :' },
        { type: 'table', rows: [['Société', 'NordX Labs Oy'], ['Identifiant fiscal (Y-tunnus)', '3615236-4'], ['E-mail', 'hello@animlearn.com']] },
      ]},
      { num: '2', title: 'Données que nous collectons', blocks: [
        { type: 'table', rows: [
          ['Compte', 'Nom complet, adresse e-mail, langue préférée, date de création du compte'],
          ['Connexion Google (optionnel)', "ID utilisateur Google, URL de la photo de profil, nom et e-mail via Google OAuth"],
          ['Activité d\'apprentissage', "Pourcentage de visionnage vidéo, scores de maîtrise des concepts, tentatives d'exercices et réponses, feedback IA, temps passé"],
          ['Historique des chats', "Conversations de résolution de problèmes avec le tuteur IA"],
          ['Journaux de sécurité', "Adresse IP, user-agent du navigateur — enregistrés lors de la connexion pour prévenir la fraude. Conservés 90 jours puis supprimés automatiquement."],
        ]},
      ]},
      { num: '3', title: 'Base juridique du traitement', blocks: [
        { type: 'p', text: "Le traitement des données personnelles dans LearnX-AI est basé sur l'intérêt public et l'exercice de l'autorité officielle (RGPD Article 6(1)(e)), dans le cadre des activités éducatives de l'école." },
        { type: 'p', text: "La journalisation de sécurité est basée sur notre intérêt légitime (Article 6(1)(f)) à prévenir les accès non autorisés et la fraude." },
      ]},
      { num: '4', title: 'Profilage et traitement automatisé', blocks: [
        { type: 'p', text: "LearnX-AI analyse automatiquement votre activité d'apprentissage pour personnaliser l'expérience éducative. Cela comprend :" },
        { type: 'ul', items: [
          "Calcul d'un score de maîtrise (0–1) par concept basé sur vos réponses aux quiz et tentatives d'exercices",
          "Suivi d'une tendance d'apprentissage (en amélioration / stable / en déclin) par concept",
          "Surveillance du taux de visionnage vidéo pour identifier les lacunes d'apprentissage",
          "Génération de questions d'exercice personnalisées basées sur vos performances",
        ]},
        { type: 'p', text: "Cela constitue un profilage au sens de l'article 4(4) du RGPD. Le profilage est effectué dans l'intérêt public dans le cadre des activités éducatives." },
      ]},
      { num: '5', title: 'Sous-traitants tiers', blocks: [
        { type: 'table', rows: [
          ['Google LLC', "Authentification Google OAuth. Données transférées : nom, e-mail, ID utilisateur Google."],
          ['Anthropic / Claude (via Google Cloud Vertex AI, UE)', "Génération de contenu IA. Hébergé sur Google Cloud dans l'UE. Aucun identifiant personnel des élèves n'est envoyé au modèle."],
          ['Microsoft Azure (UE)', "Embeddings IA pour la recherche de programme. Texte de document traité en région UE."],
          ['Cloudflare R2 (UE)', "Stockage des fichiers vidéo générés et des ressources SVG."],
          ['Supabase / PostgreSQL', "Hébergement de base de données pour toutes les données utilisateurs et d'apprentissage."],
        ]},
        { type: 'p', text: "Nous ne vendons pas de données personnelles à des tiers." },
      ]},
      { num: '6', title: 'Conservation des données', blocks: [
        { type: 'table', rows: [
          ['Données du compte', "Conservées tant que votre compte est actif. Supprimées à la demande de suppression du compte."],
          ["Activité d'apprentissage", "Conservée tant que votre compte est actif. Supprimée à la suppression du compte."],
          ['Journaux de sécurité (IP, user-agent)', "Supprimés automatiquement après 90 jours."],
          ['Vidéos générées par IA', "Conservées tant qu'elles sont liées à votre compte. Supprimées à la suppression du compte."],
        ]},
      ]},
      { num: '7', title: 'Vos droits', blocks: [
        { type: 'p', text: "En vertu du RGPD, vous disposez des droits suivants :" },
        { type: 'ul', items: [
          "Droit d'accès — demander une copie de vos données personnelles",
          "Droit de rectification — corriger les données inexactes via les Paramètres",
          "Droit à l'effacement — supprimer votre compte et toutes les données associées via Paramètres → Supprimer le compte",
          "Droit à la limitation — demander que nous limitions le traitement de vos données",
          "Droit d'opposition — vous opposer au traitement basé sur l'intérêt public",
          "Droit à la portabilité — demander vos données dans un format lisible par machine",
        ]},
        { type: 'p', text: "Pour exercer ces droits, contactez-nous à hello@animlearn.com. Nous répondrons dans les 30 jours." },
        { type: 'p', text: "Vous avez également le droit de déposer une plainte auprès du médiateur finlandais pour la protection des données (tietosuoja.fi)." },
      ]},
      { num: '8', title: 'Sécurité des données', blocks: [
        { type: 'ul', items: [
          "Les mots de passe sont hachés avec bcrypt (jamais stockés en clair)",
          "Toutes les données en transit sont chiffrées avec TLS/HTTPS",
          "Les jetons d'authentification sont stockés localement dans le navigateur et ne sont pas envoyés à des tiers",
          "L'accès aux bases de données de production est limité au personnel autorisé",
        ]},
      ]},
      { num: '9', title: 'Cookies et stockage local', blocks: [
        { type: 'p', text: "LearnX-AI n'utilise pas de cookies de suivi. Les jetons d'authentification sont stockés dans le localStorage de votre navigateur et sont utilisés uniquement pour vous maintenir connecté. Aucun cookie d'analyse ou publicitaire tiers n'est utilisé." },
      ]},
      { num: '10', title: 'Données des enfants', blocks: [
        { type: 'p', text: "LearnX-AI est conçu pour une utilisation dans les écoles, y compris par des mineurs. Les comptes des élèves sont créés et gérés dans le contexte scolaire. Les enseignants et les administrateurs scolaires sont responsables de s'assurer que les comptes des élèves respectent les lois applicables." },
        { type: 'p', text: "Nous ne collectons pas sciemment de données auprès d'enfants en dehors d'un contexte éducatif supervisé." },
      ]},
      { num: '11', title: 'Modifications de cette politique', blocks: [
        { type: 'p', text: 'Nous pouvons mettre à jour cette politique de confidentialité de temps en temps. Lorsque nous le faisons, nous mettons à jour la date "Dernière mise à jour" en haut de cette page. Les modifications importantes seront communiquées via l\'application ou par e-mail.' },
      ]},
      { num: '12', title: 'Contact', blocks: [
        { type: 'table', rows: [['Société', 'NordX Labs Oy'], ['E-mail', 'hello@animlearn.com']] },
      ]},
    ],
  },

  es: {
    title: 'Política de privacidad',
    lastUpdated: 'Última actualización: 15 de abril de 2026',
    sections: [
      { num: '1', title: 'Responsable del tratamiento', blocks: [
        { type: 'p', text: 'El responsable del tratamiento de LearnX-AI es:' },
        { type: 'table', rows: [['Empresa', 'NordX Labs Oy'], ['ID fiscal (Y-tunnus)', '3615236-4'], ['Email', 'hello@animlearn.com']] },
      ]},
      { num: '2', title: 'Datos que recopilamos', blocks: [
        { type: 'table', rows: [
          ['Cuenta', 'Nombre completo, dirección de email, idioma preferido, fecha de creación de la cuenta'],
          ['Inicio de sesión con Google (opcional)', 'ID de usuario de Google, URL de foto de perfil, nombre y email de Google OAuth'],
          ['Actividad de aprendizaje', 'Porcentaje de visualización de video, puntuaciones de dominio de conceptos, intentos de práctica y respuestas, retroalimentación de IA, tiempo dedicado'],
          ['Historial de chat', 'Conversaciones de resolución de problemas con el tutor IA'],
          ['Registros de seguridad', 'Dirección IP, user-agent del navegador — registrados en inicio de sesión para prevenir fraudes. Retenidos 90 días, luego eliminados automáticamente.'],
        ]},
      ]},
      { num: '3', title: 'Base jurídica del tratamiento', blocks: [
        { type: 'p', text: 'El tratamiento de datos personales en LearnX-AI se basa en el interés público y el ejercicio de autoridad oficial (RGPD Artículo 6(1)(e)), en relación con las actividades educativas del centro escolar.' },
        { type: 'p', text: 'El registro de seguridad se basa en nuestro interés legítimo (Artículo 6(1)(f)) en prevenir el acceso no autorizado y el fraude.' },
      ]},
      { num: '4', title: 'Elaboración de perfiles y tratamiento automatizado', blocks: [
        { type: 'p', text: 'LearnX-AI analiza automáticamente tu actividad de aprendizaje para personalizar la experiencia educativa. Esto incluye:' },
        { type: 'ul', items: [
          'Calcular una puntuación de dominio (0–1) por concepto basada en tus respuestas al quiz y intentos de práctica',
          'Seguimiento de una tendencia de aprendizaje (mejorando / estable / declinando) por concepto',
          'Monitoreo del porcentaje de visualización de video para identificar lagunas de aprendizaje',
          'Generación de preguntas de práctica personalizadas basadas en tu rendimiento',
        ]},
        { type: 'p', text: 'Esto constituye elaboración de perfiles conforme al Artículo 4(4) del RGPD. La elaboración de perfiles se realiza en interés público como parte de las actividades educativas.' },
      ]},
      { num: '5', title: 'Encargados del tratamiento terceros', blocks: [
        { type: 'table', rows: [
          ['Google LLC', 'Autenticación Google OAuth. Datos transferidos: nombre, email, ID de usuario de Google.'],
          ['Anthropic / Claude (vía Google Cloud Vertex AI, UE)', 'Generación de contenido IA. Alojado en Google Cloud dentro de la UE. No se envían identificadores personales de estudiantes al modelo.'],
          ['Microsoft Azure (UE)', 'Embeddings de IA para búsqueda de programa de estudios. Texto de documentos procesado en región UE.'],
          ['Cloudflare R2 (UE)', 'Almacenamiento de archivos de video generados y recursos SVG.'],
          ['Supabase / PostgreSQL', 'Alojamiento de base de datos para todos los datos de usuarios y aprendizaje.'],
        ]},
        { type: 'p', text: 'No vendemos datos personales a terceros.' },
      ]},
      { num: '6', title: 'Conservación de datos', blocks: [
        { type: 'table', rows: [
          ['Datos de cuenta', 'Retenidos mientras tu cuenta esté activa. Eliminados al solicitar la eliminación de la cuenta.'],
          ['Actividad de aprendizaje', 'Retenida mientras tu cuenta esté activa. Eliminada al eliminar la cuenta.'],
          ['Registros de seguridad (IP, user-agent)', 'Eliminados automáticamente después de 90 días.'],
          ['Videos generados por IA', 'Retenidos mientras estén vinculados a tu cuenta. Eliminados al eliminar la cuenta.'],
        ]},
      ]},
      { num: '7', title: 'Tus derechos', blocks: [
        { type: 'p', text: 'En virtud del RGPD, tienes los siguientes derechos:' },
        { type: 'ul', items: [
          'Derecho de acceso — solicitar una copia de tus datos personales',
          'Derecho de rectificación — corregir datos inexactos a través de Configuración',
          'Derecho de supresión — eliminar tu cuenta y todos los datos asociados a través de Configuración → Eliminar cuenta',
          'Derecho a la limitación — solicitar que limitemos el tratamiento de tus datos',
          'Derecho de oposición — oponerte al tratamiento basado en el interés público',
          'Derecho a la portabilidad — solicitar tus datos en formato legible por máquina',
        ]},
        { type: 'p', text: 'Para ejercer estos derechos, contáctanos en hello@animlearn.com. Responderemos en 30 días.' },
        { type: 'p', text: 'También tienes derecho a presentar una reclamación ante el Defensor del Pueblo para la Protección de Datos de Finlandia (tietosuoja.fi).' },
      ]},
      { num: '8', title: 'Seguridad de los datos', blocks: [
        { type: 'ul', items: [
          'Las contraseñas se procesan con bcrypt (nunca se almacenan en texto plano)',
          'Todos los datos en tránsito se cifran con TLS/HTTPS',
          'Los tokens de autenticación se almacenan localmente en el navegador y no se envían a terceros',
          'El acceso a las bases de datos de producción está limitado al personal autorizado',
        ]},
      ]},
      { num: '9', title: 'Cookies y almacenamiento local', blocks: [
        { type: 'p', text: 'LearnX-AI no utiliza cookies de seguimiento. Los tokens de autenticación se almacenan en el localStorage de tu navegador y se utilizan únicamente para mantenerte conectado. No se utilizan cookies de análisis ni publicidad de terceros.' },
      ]},
      { num: '10', title: 'Datos de menores', blocks: [
        { type: 'p', text: 'LearnX-AI está diseñado para su uso en escuelas, incluso por menores. Las cuentas de los estudiantes son creadas y gestionadas en el contexto escolar. Los profesores y administradores escolares son responsables de garantizar que las cuentas de los estudiantes cumplan con las leyes aplicables.' },
        { type: 'p', text: 'No recopilamos conscientemente datos de menores fuera de un contexto educativo supervisado.' },
      ]},
      { num: '11', title: 'Cambios en esta política', blocks: [
        { type: 'p', text: 'Podemos actualizar esta política de privacidad de vez en cuando. Cuando lo hagamos, actualizaremos la fecha de "Última actualización" en la parte superior de esta página. Los cambios importantes se comunicarán a través de la aplicación o por email.' },
      ]},
      { num: '12', title: 'Contacto', blocks: [
        { type: 'table', rows: [['Empresa', 'NordX Labs Oy'], ['Email', 'hello@animlearn.com']] },
      ]},
    ],
  },
};

function DataTable({ rows }: { rows: [string, string][] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--bd)]">
      <table className="w-full text-sm">
        <tbody>
          {rows.map(([label, value], i) => (
            <tr key={i} className="border-b border-[var(--bd)] last:border-0">
              <td className="px-4 py-2.5 font-medium text-[var(--tx2)] align-top bg-[var(--surface)] whitespace-nowrap w-44">{label}</td>
              <td className="px-4 py-2.5 text-[var(--tx4)]">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderBlock(block: Block, key: number) {
  if (block.type === 'p')     return <p key={key} className="text-[var(--tx3)]">{block.text}</p>;
  if (block.type === 'ul')    return <ul key={key} className="list-disc list-inside space-y-1 text-[var(--tx4)]">{block.items.map((item, i) => <li key={i}>{item}</li>)}</ul>;
  if (block.type === 'table') return <DataTable key={key} rows={block.rows as [string, string][]} />;
}

export default function PrivacyPolicyPage() {
  const { language } = useLanguageStore();
  const c = CONTENT[language] ?? CONTENT.en;

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--tx1)]">
      <div className="sticky top-0 z-10 border-b border-[var(--bd)] bg-[var(--surface)]/80 backdrop-blur-sm">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 h-12 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-1.5 text-sm text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors">
            <ArrowLeft size={14} /> Back to app
          </Link>
          <div className="flex items-center gap-2">
            <img src="/logo-36.png" alt="LearnX-AI" className="w-5 h-5 object-contain" />
            <span className="text-[var(--tx6)] text-xs">learnx-ai.com</span>
          </div>
        </div>
      </div>

      <main className="max-w-2xl mx-auto px-4 sm:px-6 py-12">
        <header className="mb-10">
          <p className="text-xs uppercase tracking-widest text-[var(--tx7)] font-medium mb-2">Legal</p>
          <h1 className="text-3xl font-bold text-[var(--tx1)] mb-2">{c.title}</h1>
          <p className="text-[var(--tx6)] text-sm">{c.lastUpdated}</p>
        </header>

        <div className="space-y-8">
          {c.sections.map(section => (
            <section key={section.num} className="space-y-3">
              <h2 className="text-[var(--tx1)] font-semibold text-base flex items-baseline gap-2">
                <span className="text-[var(--tx7)] font-normal text-sm w-6 shrink-0">{section.num}.</span>
                {section.title}
              </h2>
              <div className="text-sm leading-relaxed space-y-2.5 pl-7">
                {section.blocks.map((block, i) => renderBlock(block, i))}
              </div>
            </section>
          ))}
        </div>
      </main>

      <footer className="border-t border-[var(--bd)] py-8 mt-12">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center gap-4 justify-between">
          <div className="flex items-center gap-2">
            <img src="/logo-36.png" alt="LearnX-AI" className="w-5 h-5 object-contain" />
            <span className="text-[var(--tx6)] text-xs">NordX Labs Oy · Business ID: 3615236-4 · Espoo, Finland</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/privacy" className="text-purple-400 text-xs">Privacy Policy</Link>
            <Link href="/terms" className="text-[var(--tx6)] hover:text-[var(--tx1)] text-xs transition-colors">Terms of Service</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
