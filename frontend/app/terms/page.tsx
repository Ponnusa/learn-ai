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
type Content = { title: string; lastUpdated: string; intro: string; sections: Section[] };

const CONTENT: Record<string, Content> = {
  en: {
    title: 'Terms of Service',
    lastUpdated: 'Last updated: 15 April 2026',
    intro: 'By using LearnX-AI, you agree to these terms. Please read them carefully.',
    sections: [
      { num: '1', title: 'About LearnX-AI', blocks: [
        { type: 'p', text: 'LearnX-AI is an AI-powered learning platform operated by NordX Labs Oy, a Finnish company (Y-tunnus: 3615236-4). The platform provides AI-generated educational videos, interactive exercises, and AI-assisted tutoring for schools and students.' },
      ]},
      { num: '2', title: 'Who Can Use LearnX-AI', blocks: [
        { type: 'p', text: 'LearnX-AI is designed for use within schools and educational institutions. Accounts are issued to:' },
        { type: 'ul', items: [
          'Students enrolled at a participating school',
          'Teachers employed at a participating school',
          'School administrators',
        ]},
        { type: 'p', text: 'Accounts are not transferable. You must not share your login credentials with others.' },
      ]},
      { num: '3', title: 'Acceptable Use', blocks: [
        { type: 'p', text: 'You agree not to:' },
        { type: 'ul', items: [
          'Use the platform for any purpose other than educational activities',
          'Attempt to reverse-engineer, scrape, or extract AI-generated content at scale',
          'Upload or share any content that is unlawful, harmful, or violates third-party rights',
          'Attempt to circumvent safety filters or generate inappropriate content',
          'Share your account credentials or allow others to use your account',
          'Use the platform in any way that could damage, disable, or overload the service',
        ]},
      ]},
      { num: '4', title: 'AI Content Disclaimer', blocks: [
        { type: 'p', text: 'LearnX-AI uses artificial intelligence to generate educational videos, explanations, and feedback. While we strive for accuracy:' },
        { type: 'ul', items: [
          'AI-generated content may contain errors, inaccuracies, or omissions',
          'Content should not be relied upon as the sole source for critical decisions',
          'Teachers are responsible for verifying AI-generated content before using it in formal assessments',
        ]},
        { type: 'p', text: 'The AI tutor is designed to assist learning, not to replace qualified teachers.' },
      ]},
      { num: '5', title: 'Teacher Responsibilities', blocks: [
        { type: 'p', text: 'Teachers using LearnX-AI agree to:' },
        { type: 'ul', items: [
          'Review AI-generated content for accuracy before presenting it to students',
          'Ensure appropriate use of the platform within their classrooms',
          'Manage student accounts responsibly and in accordance with school policy',
          'Not use student learning data for purposes outside of educational support',
        ]},
      ]},
      { num: '6', title: 'Intellectual Property', blocks: [
        { type: 'p', text: 'All content, software, and technology on LearnX-AI — including AI models, video generation pipelines, and the platform interface — is owned by NordX Labs Oy or its licensors.' },
        { type: 'p', text: 'AI-generated videos and content created using LearnX-AI tools may be used for educational purposes within the school. You may not resell, sublicense, or distribute them beyond your educational institution without written permission.' },
        { type: 'p', text: 'Your own submissions (uploaded materials, course content) remain your intellectual property.' },
      ]},
      { num: '7', title: 'Privacy', blocks: [
        { type: 'p', text: 'Your use of LearnX-AI is also governed by our Privacy Policy, available at learnx-ai.com/privacy. By using the platform, you agree to the collection and processing of data as described in the Privacy Policy.' },
      ]},
      { num: '8', title: 'Service Availability', blocks: [
        { type: 'p', text: 'We aim to provide a reliable service, but we do not guarantee uninterrupted or error-free operation. We may:' },
        { type: 'ul', items: [
          'Perform scheduled maintenance (with advance notice where possible)',
          'Update or modify features of the platform',
          'Temporarily suspend access for technical reasons',
        ]},
        { type: 'p', text: 'We are not liable for any loss or inconvenience caused by temporary unavailability of the service.' },
      ]},
      { num: '9', title: 'Limitation of Liability', blocks: [
        { type: 'p', text: 'To the maximum extent permitted by law, NordX Labs Oy is not liable for:' },
        { type: 'ul', items: [
          'Any indirect, incidental, or consequential damages',
          'Loss of data, profits, or educational outcomes resulting from use or inability to use the service',
          'Errors or inaccuracies in AI-generated educational content',
        ]},
        { type: 'p', text: 'Our total liability to you for any claim arising from use of the service is limited to the fees paid by your institution in the 12 months preceding the claim.' },
      ]},
      { num: '10', title: 'Account Termination', blocks: [
        { type: 'p', text: 'Accounts may be terminated or suspended:' },
        { type: 'ul', items: [
          'By the user at any time via Settings → Delete Account',
          'By school administrators managing institutional accounts',
          'By NordX Labs Oy for violation of these terms',
          'Automatically when a school\'s subscription ends',
        ]},
        { type: 'p', text: 'Upon termination, your personal data will be deleted in accordance with our Privacy Policy.' },
      ]},
      { num: '11', title: 'Governing Law', blocks: [
        { type: 'p', text: 'These terms are governed by the laws of Finland. Any disputes shall be resolved in the district court of Espoo, Finland, unless mandatory local consumer law requires otherwise.' },
      ]},
      { num: '12', title: 'Changes to Terms', blocks: [
        { type: 'p', text: 'We may update these terms from time to time. We will notify you of material changes via the platform or by email. Continued use of the service after notification constitutes acceptance of the new terms.' },
      ]},
      { num: '13', title: 'Contact', blocks: [
        { type: 'table', rows: [['Company', 'NordX Labs Oy'], ['Email', 'hello@animlearn.com'], ['Business ID', '3615236-4']] },
      ]},
    ],
  },

  fi: {
    title: 'Käyttöehdot',
    lastUpdated: 'Viimeksi päivitetty: 15. huhtikuuta 2026',
    intro: 'Käyttämällä LearnX-AI:ta hyväksyt nämä ehdot. Lue ne huolellisesti.',
    sections: [
      { num: '1', title: 'LearnX-AI:sta', blocks: [
        { type: 'p', text: 'LearnX-AI on tekoälypohjainen oppimisalusta, jota hallinnoi NordX Labs Oy, suomalainen yritys (Y-tunnus: 3615236-4). Alusta tarjoaa tekoälyn luomia oppimisvideoita, interaktiivisia harjoituksia ja tekoälyavusteista opetusta kouluille ja opiskelijoille.' },
      ]},
      { num: '2', title: 'Kuka voi käyttää LearnX-AI:ta', blocks: [
        { type: 'p', text: 'LearnX-AI on suunniteltu käytettäväksi kouluissa ja oppilaitoksissa. Tilejä myönnetään:' },
        { type: 'ul', items: [
          'Osallistuvan koulun opiskelijoille',
          'Osallistuvan koulun opettajille',
          'Koulun ylläpitäjille',
        ]},
        { type: 'p', text: 'Tilejä ei voi siirtää toiselle. Et saa jakaa kirjautumistietojasi muille.' },
      ]},
      { num: '3', title: 'Hyväksyttävä käyttö', blocks: [
        { type: 'p', text: 'Sitoudut olemaan:' },
        { type: 'ul', items: [
          'Käyttämättä alustaa muuhun kuin oppimistoimintaan',
          'Yrittämättä purkaa, kaapata tai poimia tekoälyn luomaa sisältöä laajamittaisesti',
          'Lataamatta tai jakamatta sisältöä, joka on laitonta, haitallista tai loukkaa kolmannen osapuolen oikeuksia',
          'Yrittämättä kiertää turvasuodattimia tai luoda sopimatonta sisältöä',
          'Jakamatta tilitietojasi tai sallitta muiden käyttää tiliäsi',
          'Käyttämättä alustaa tavalla, joka voi vahingoittaa, poistaa käytöstä tai ylikuormittaa palvelua',
        ]},
      ]},
      { num: '4', title: 'Tekoälysisällön vastuuvapauslauseke', blocks: [
        { type: 'p', text: 'LearnX-AI käyttää tekoälyä oppimisvideoiden, selitysten ja palautteen luomiseen. Vaikka pyrimme tarkkuuteen:' },
        { type: 'ul', items: [
          'Tekoälyn luoma sisältö voi sisältää virheitä, epätarkkuuksia tai puutteita',
          'Sisältöön ei tule luottaa ainoana lähteenä kriittisiä päätöksiä tehtäessä',
          'Opettajat vastaavat tekoälyn luoman sisällön tarkistamisesta ennen sen käyttöä virallisissa arvioinneissa',
        ]},
        { type: 'p', text: 'Tekoälytutor on suunniteltu oppimisen tukemiseksi, ei pätevien opettajien korvaamiseksi.' },
      ]},
      { num: '5', title: 'Opettajien vastuut', blocks: [
        { type: 'p', text: 'LearnX-AI:ta käyttävät opettajat sitoutuvat:' },
        { type: 'ul', items: [
          'Tarkistamaan tekoälyn luoman sisällön tarkkuuden ennen sen esittämistä opiskelijoille',
          'Varmistamaan alustan asianmukaisen käytön luokkahuoneissaan',
          'Hallitsemaan opiskelijatilejä vastuullisesti ja koulun käytäntöjen mukaisesti',
          'Olemaan käyttämättä opiskelijoiden oppimistietoja muuhun kuin oppimistuen tarkoituksiin',
        ]},
      ]},
      { num: '6', title: 'Immateriaalioikeudet', blocks: [
        { type: 'p', text: 'Kaikki LearnX-AI:n sisältö, ohjelmistot ja teknologia — mukaan lukien tekoälymallit, videontekoprosessit ja alustan käyttöliittymä — ovat NordX Labs Oy:n tai sen lisenssinantajien omaisuutta.' },
        { type: 'p', text: 'LearnX-AI-työkaluilla luotuja tekoälyvideoita ja sisältöä voidaan käyttää koulussa opetustarkoituksiin. Et saa myydä, lisensoida edelleen tai jakaa niitä oppilaitoksesi ulkopuolelle ilman kirjallista lupaa.' },
        { type: 'p', text: 'Omat lähetyksesi (ladatut materiaalit, kurssimateriaalit) pysyvät immateriaalioikeutesi alaisina.' },
      ]},
      { num: '7', title: 'Tietosuoja', blocks: [
        { type: 'p', text: 'LearnX-AI:n käyttöä säätelee myös tietosuojaselosteemme, joka on saatavilla osoitteessa learnx-ai.com/privacy. Käyttämällä alustaa hyväksyt tietosuojaselosteessa kuvatun tietojen keräämisen ja käsittelyn.' },
      ]},
      { num: '8', title: 'Palvelun saatavuus', blocks: [
        { type: 'p', text: 'Pyrimme tarjoamaan luotettavan palvelun, mutta emme takaa keskeytymätöntä tai virheetöntä toimintaa. Saatamme:' },
        { type: 'ul', items: [
          'Suorittaa suunniteltua ylläpitoa (etukäteen ilmoittaen mahdollisuuksien mukaan)',
          'Päivittää tai muokata alustan ominaisuuksia',
          'Keskeyttää väliaikaisesti pääsyn teknisistä syistä',
        ]},
        { type: 'p', text: 'Emme ole vastuussa palvelun tilapäisestä saatavuusongelmasta aiheutuneista vahingoista tai haitoista.' },
      ]},
      { num: '9', title: 'Vastuunrajoitus', blocks: [
        { type: 'p', text: 'Lain sallimassa laajuudessa NordX Labs Oy ei ole vastuussa:' },
        { type: 'ul', items: [
          'Epäsuorista, satunnaisista tai seurannaisvahingoista',
          'Tietojen, tuottojen tai oppimistulosten menetyksistä, jotka johtuvat palvelun käytöstä tai käyttökyvyttömyydestä',
          'Virheistä tai epätarkkuuksista tekoälyn luomassa oppimissisällössä',
        ]},
        { type: 'p', text: 'Kokonaisvastuumme sinulle mistä tahansa palvelun käytöstä johtuvasta vaatimuksesta rajoittuu oppilaitoksesi vaatimusta edeltäneiden 12 kuukauden aikana maksamiin maksuihin.' },
      ]},
      { num: '10', title: 'Tilin sulkeminen', blocks: [
        { type: 'p', text: 'Tilit voidaan sulkea tai jäädyttää:' },
        { type: 'ul', items: [
          'Käyttäjän toimesta milloin tahansa Asetukset → Poista tili -toiminnon kautta',
          'Koulun ylläpitäjien toimesta oppilaitostilien hallinnassa',
          'NordX Labs Oy:n toimesta näiden ehtojen rikkomisen vuoksi',
          'Automaattisesti, kun koulun tilaus päättyy',
        ]},
        { type: 'p', text: 'Tilin sulkemisen yhteydessä henkilötietosi poistetaan tietosuojaselosteen mukaisesti.' },
      ]},
      { num: '11', title: 'Sovellettava laki', blocks: [
        { type: 'p', text: 'Näitä ehtoja sovelletaan Suomen lakien mukaisesti. Mahdolliset riidat ratkaistaan Espoon käräjäoikeudessa, ellei pakollinen paikallinen kuluttajansuojalainsäädäntö vaadi muuta.' },
      ]},
      { num: '12', title: 'Muutokset ehtoihin', blocks: [
        { type: 'p', text: 'Saatamme päivittää näitä ehtoja ajoittain. Ilmoitamme olennaisista muutoksista alustan kautta tai sähköpostitse. Jatkamalla palvelun käyttöä ilmoituksen jälkeen hyväksyt uudet ehdot.' },
      ]},
      { num: '13', title: 'Yhteystiedot', blocks: [
        { type: 'table', rows: [['Yritys', 'NordX Labs Oy'], ['Sähköposti', 'hello@animlearn.com'], ['Y-tunnus', '3615236-4']] },
      ]},
    ],
  },

  sv: {
    title: 'Användarvillkor',
    lastUpdated: 'Senast uppdaterad: 15 april 2026',
    intro: 'Genom att använda LearnX-AI godkänner du dessa villkor. Läs dem noggrant.',
    sections: [
      { num: '1', title: 'Om LearnX-AI', blocks: [
        { type: 'p', text: 'LearnX-AI är en AI-driven inlärningsplattform som drivs av NordX Labs Oy, ett finskt företag (Y-tunnus: 3615236-4). Plattformen tillhandahåller AI-genererade utbildningsvideor, interaktiva övningar och AI-assisterad handledning för skolor och elever.' },
      ]},
      { num: '2', title: 'Vem kan använda LearnX-AI', blocks: [
        { type: 'p', text: 'LearnX-AI är utformat för användning inom skolor och utbildningsinstitutioner. Konton utfärdas till:' },
        { type: 'ul', items: [
          'Elever inskrivna vid en deltagande skola',
          'Lärare anställda vid en deltagande skola',
          'Skoladministratörer',
        ]},
        { type: 'p', text: 'Konton är inte överlåtbara. Du får inte dela dina inloggningsuppgifter med andra.' },
      ]},
      { num: '3', title: 'Godtagbar användning', blocks: [
        { type: 'p', text: 'Du godkänner att inte:' },
        { type: 'ul', items: [
          'Använda plattformen för annat än utbildningsändamål',
          'Försöka bakåtkompilera, skrapa eller extrahera AI-genererat innehåll i stor skala',
          'Ladda upp eller dela innehåll som är olagligt, skadligt eller kränker tredje parts rättigheter',
          'Försöka kringgå säkerhetsfilter eller generera olämpligt innehåll',
          'Dela dina kontouppgifter eller tillåta andra att använda ditt konto',
          'Använda plattformen på ett sätt som kan skada, inaktivera eller överbelasta tjänsten',
        ]},
      ]},
      { num: '4', title: 'Friskrivning för AI-innehåll', blocks: [
        { type: 'p', text: 'LearnX-AI använder artificiell intelligens för att generera utbildningsvideor, förklaringar och feedback. Även om vi strävar efter noggrannhet:' },
        { type: 'ul', items: [
          'Kan AI-genererat innehåll innehålla fel, felaktigheter eller utelämnanden',
          'Bör innehåll inte förlitas på som enda källa för kritiska beslut',
          'Är lärare ansvariga för att verifiera AI-genererat innehåll innan det används i formella bedömningar',
        ]},
        { type: 'p', text: 'AI-handledaren är utformad för att stödja lärande, inte ersätta kvalificerade lärare.' },
      ]},
      { num: '5', title: 'Lärarnas ansvar', blocks: [
        { type: 'p', text: 'Lärare som använder LearnX-AI godkänner att:' },
        { type: 'ul', items: [
          'Granska AI-genererat innehåll för noggrannhet innan det presenteras för elever',
          'Säkerställa lämplig användning av plattformen i sina klassrum',
          'Hantera elevkonton ansvarsfullt och i enlighet med skolans policy',
          'Inte använda elevers inlärningsdata för andra syften än utbildningsstöd',
        ]},
      ]},
      { num: '6', title: 'Immateriella rättigheter', blocks: [
        { type: 'p', text: 'Allt innehåll, programvara och teknik på LearnX-AI — inklusive AI-modeller, videogenereringspipelines och plattformsgränssnittet — ägs av NordX Labs Oy eller dess licensgivare.' },
        { type: 'p', text: 'AI-genererade videor och innehåll som skapats med LearnX-AI-verktyg kan användas för utbildningsändamål inom skolan. Du får inte sälja vidare, underlicensiera eller distribuera dem utanför din utbildningsinstitution utan skriftligt tillstånd.' },
        { type: 'p', text: 'Dina egna inlämningar (uppladdade material, kursinnehåll) förblir din immateriella egendom.' },
      ]},
      { num: '7', title: 'Integritet', blocks: [
        { type: 'p', text: 'Din användning av LearnX-AI regleras också av vår integritetspolicy, tillgänglig på learnx-ai.com/privacy. Genom att använda plattformen godkänner du insamling och behandling av data som beskrivs i integritetspolicyn.' },
      ]},
      { num: '8', title: 'Tjänstens tillgänglighet', blocks: [
        { type: 'p', text: 'Vi strävar efter att tillhandahålla en tillförlitlig tjänst, men vi garanterar inte oavbruten eller felfri drift. Vi kan:' },
        { type: 'ul', items: [
          'Utföra schemalagt underhåll (med förhandsbesked när möjligt)',
          'Uppdatera eller modifiera plattformens funktioner',
          'Tillfälligt avbryta åtkomst av tekniska skäl',
        ]},
        { type: 'p', text: 'Vi är inte ansvariga för förlust eller olägenheter orsakade av tillfällig otillgänglighet av tjänsten.' },
      ]},
      { num: '9', title: 'Ansvarsbegränsning', blocks: [
        { type: 'p', text: 'I den utsträckning lagen tillåter är NordX Labs Oy inte ansvarig för:' },
        { type: 'ul', items: [
          'Indirekta, tillfälliga eller följdskador',
          'Förlust av data, vinster eller utbildningsresultat till följd av användning eller oförmåga att använda tjänsten',
          'Fel eller felaktigheter i AI-genererat utbildningsinnehåll',
        ]},
        { type: 'p', text: 'Vårt totala ansvar gentemot dig för krav som uppstår från användning av tjänsten är begränsat till de avgifter som din institution betalat under de 12 månaderna som föregår kravet.' },
      ]},
      { num: '10', title: 'Kontoavstängning', blocks: [
        { type: 'p', text: 'Konton kan avslutas eller pausas:' },
        { type: 'ul', items: [
          'Av användaren när som helst via Inställningar → Radera konto',
          'Av skoladministratörer som hanterar institutionskonton',
          'Av NordX Labs Oy vid brott mot dessa villkor',
          'Automatiskt när en skolas prenumeration upphör',
        ]},
        { type: 'p', text: 'Vid kontoavstängning raderas dina personuppgifter i enlighet med vår integritetspolicy.' },
      ]},
      { num: '11', title: 'Tillämplig lag', blocks: [
        { type: 'p', text: 'Dessa villkor regleras av finsk lag. Eventuella tvister ska lösas i Esbo tingsrätt, Finland, om inte obligatorisk lokal konsumentlagstiftning kräver annat.' },
      ]},
      { num: '12', title: 'Ändringar av villkor', blocks: [
        { type: 'p', text: 'Vi kan uppdatera dessa villkor från tid till annan. Vi meddelar dig om väsentliga ändringar via plattformen eller via e-post. Fortsatt användning av tjänsten efter meddelande innebär godkännande av de nya villkoren.' },
      ]},
      { num: '13', title: 'Kontakt', blocks: [
        { type: 'table', rows: [['Företag', 'NordX Labs Oy'], ['E-post', 'hello@animlearn.com'], ['Företags-ID', '3615236-4']] },
      ]},
    ],
  },

  fr: {
    title: "Conditions d'utilisation",
    lastUpdated: 'Dernière mise à jour : 15 avril 2026',
    intro: "En utilisant LearnX-AI, vous acceptez ces conditions. Veuillez les lire attentivement.",
    sections: [
      { num: '1', title: 'À propos de LearnX-AI', blocks: [
        { type: 'p', text: "LearnX-AI est une plateforme d'apprentissage basée sur l'IA, exploitée par NordX Labs Oy, une société finlandaise (Y-tunnus : 3615236-4). La plateforme fournit des vidéos éducatives générées par IA, des exercices interactifs et un tutorat assisté par IA pour les écoles et les étudiants." },
      ]},
      { num: '2', title: 'Qui peut utiliser LearnX-AI', blocks: [
        { type: 'p', text: "LearnX-AI est conçu pour être utilisé dans les écoles et les établissements d'enseignement. Les comptes sont délivrés aux :" },
        { type: 'ul', items: [
          "Étudiants inscrits dans une école participante",
          "Enseignants employés dans une école participante",
          "Administrateurs scolaires",
        ]},
        { type: 'p', text: "Les comptes ne sont pas transférables. Vous ne devez pas partager vos identifiants de connexion avec d'autres personnes." },
      ]},
      { num: '3', title: 'Utilisation acceptable', blocks: [
        { type: 'p', text: "Vous vous engagez à ne pas :" },
        { type: 'ul', items: [
          "Utiliser la plateforme à d'autres fins qu'éducatives",
          "Tenter d'effectuer de l'ingénierie inverse, du scraping ou d'extraire du contenu généré par IA à grande échelle",
          "Télécharger ou partager du contenu illégal, nuisible ou qui viole les droits de tiers",
          "Tenter de contourner les filtres de sécurité ou de générer du contenu inapproprié",
          "Partager vos identifiants de compte ou permettre à d'autres d'utiliser votre compte",
          "Utiliser la plateforme d'une manière qui pourrait endommager, désactiver ou surcharger le service",
        ]},
      ]},
      { num: '4', title: "Avertissement sur le contenu IA", blocks: [
        { type: 'p', text: "LearnX-AI utilise l'intelligence artificielle pour générer des vidéos éducatives, des explications et des retours. Bien que nous nous efforcions à l'exactitude :" },
        { type: 'ul', items: [
          "Le contenu généré par IA peut contenir des erreurs, des inexactitudes ou des omissions",
          "Le contenu ne doit pas être utilisé comme seule source pour des décisions critiques",
          "Les enseignants sont responsables de vérifier le contenu généré par IA avant de l'utiliser dans des évaluations formelles",
        ]},
        { type: 'p', text: "Le tuteur IA est conçu pour aider l'apprentissage, et non pour remplacer des enseignants qualifiés." },
      ]},
      { num: '5', title: "Responsabilités des enseignants", blocks: [
        { type: 'p', text: "Les enseignants utilisant LearnX-AI s'engagent à :" },
        { type: 'ul', items: [
          "Vérifier l'exactitude du contenu généré par IA avant de le présenter aux élèves",
          "Assurer une utilisation appropriée de la plateforme dans leurs classes",
          "Gérer les comptes des élèves de manière responsable et conformément à la politique scolaire",
          "Ne pas utiliser les données d'apprentissage des élèves à des fins autres que le soutien éducatif",
        ]},
      ]},
      { num: '6', title: "Propriété intellectuelle", blocks: [
        { type: 'p', text: "Tout le contenu, les logiciels et la technologie sur LearnX-AI — y compris les modèles IA, les pipelines de génération vidéo et l'interface de la plateforme — appartiennent à NordX Labs Oy ou à ses concédants de licence." },
        { type: 'p', text: "Les vidéos et contenus générés par IA créés avec les outils LearnX-AI peuvent être utilisés à des fins éducatives au sein de l'école. Vous ne pouvez pas les revendre, sous-licencier ou distribuer au-delà de votre établissement d'enseignement sans autorisation écrite." },
        { type: 'p', text: "Vos propres soumissions (matériaux téléchargés, contenu de cours) restent votre propriété intellectuelle." },
      ]},
      { num: '7', title: "Confidentialité", blocks: [
        { type: 'p', text: "Votre utilisation de LearnX-AI est également régie par notre politique de confidentialité, disponible sur learnx-ai.com/privacy. En utilisant la plateforme, vous consentez à la collecte et au traitement des données tels que décrits dans la politique de confidentialité." },
      ]},
      { num: '8', title: "Disponibilité du service", blocks: [
        { type: 'p', text: "Nous nous efforçons de fournir un service fiable, mais nous ne garantissons pas un fonctionnement ininterrompu ou sans erreur. Nous pouvons :" },
        { type: 'ul', items: [
          "Effectuer une maintenance planifiée (avec préavis dans la mesure du possible)",
          "Mettre à jour ou modifier les fonctionnalités de la plateforme",
          "Suspendre temporairement l'accès pour des raisons techniques",
        ]},
        { type: 'p', text: "Nous ne sommes pas responsables des pertes ou inconvénients causés par l'indisponibilité temporaire du service." },
      ]},
      { num: '9', title: "Limitation de responsabilité", blocks: [
        { type: 'p', text: "Dans la mesure maximale permise par la loi, NordX Labs Oy n'est pas responsable de :" },
        { type: 'ul', items: [
          "Tout dommage indirect, accessoire ou consécutif",
          "La perte de données, de profits ou de résultats éducatifs résultant de l'utilisation ou de l'impossibilité d'utiliser le service",
          "Les erreurs ou inexactitudes dans le contenu éducatif généré par IA",
        ]},
        { type: 'p', text: "Notre responsabilité totale envers vous pour toute réclamation découlant de l'utilisation du service est limitée aux frais payés par votre institution au cours des 12 mois précédant la réclamation." },
      ]},
      { num: '10', title: "Résiliation du compte", blocks: [
        { type: 'p', text: "Les comptes peuvent être résiliés ou suspendus :" },
        { type: 'ul', items: [
          "Par l'utilisateur à tout moment via Paramètres → Supprimer le compte",
          "Par les administrateurs scolaires gérant les comptes institutionnels",
          "Par NordX Labs Oy en cas de violation de ces conditions",
          "Automatiquement lorsque l'abonnement d'une école prend fin",
        ]},
        { type: 'p', text: "Lors de la résiliation, vos données personnelles seront supprimées conformément à notre politique de confidentialité." },
      ]},
      { num: '11', title: "Loi applicable", blocks: [
        { type: 'p', text: "Ces conditions sont régies par les lois de la Finlande. Tout litige sera résolu au tribunal de district d'Espoo, en Finlande, sauf si la loi locale obligatoire sur la protection des consommateurs l'exige autrement." },
      ]},
      { num: '12', title: "Modifications des conditions", blocks: [
        { type: 'p', text: "Nous pouvons mettre à jour ces conditions de temps en temps. Nous vous informerons des changements importants via la plateforme ou par e-mail. La poursuite de l'utilisation du service après notification constitue l'acceptation des nouvelles conditions." },
      ]},
      { num: '13', title: "Contact", blocks: [
        { type: 'table', rows: [['Société', 'NordX Labs Oy'], ['E-mail', 'hello@animlearn.com'], ['ID fiscal', '3615236-4']] },
      ]},
    ],
  },

  es: {
    title: 'Términos de servicio',
    lastUpdated: 'Última actualización: 15 de abril de 2026',
    intro: 'Al usar LearnX-AI, aceptas estos términos. Por favor, léelos detenidamente.',
    sections: [
      { num: '1', title: 'Acerca de LearnX-AI', blocks: [
        { type: 'p', text: 'LearnX-AI es una plataforma de aprendizaje impulsada por IA, operada por NordX Labs Oy, una empresa finlandesa (Y-tunnus: 3615236-4). La plataforma proporciona videos educativos generados por IA, ejercicios interactivos y tutoría asistida por IA para escuelas y estudiantes.' },
      ]},
      { num: '2', title: 'Quién puede usar LearnX-AI', blocks: [
        { type: 'p', text: 'LearnX-AI está diseñado para su uso en escuelas e instituciones educativas. Las cuentas se emiten a:' },
        { type: 'ul', items: [
          'Estudiantes matriculados en una escuela participante',
          'Profesores empleados en una escuela participante',
          'Administradores escolares',
        ]},
        { type: 'p', text: 'Las cuentas no son transferibles. No debes compartir tus credenciales de inicio de sesión con otros.' },
      ]},
      { num: '3', title: 'Uso aceptable', blocks: [
        { type: 'p', text: 'Aceptas no:' },
        { type: 'ul', items: [
          'Usar la plataforma para fines distintos a actividades educativas',
          'Intentar aplicar ingeniería inversa, raspar o extraer contenido generado por IA a gran escala',
          'Subir o compartir contenido que sea ilegal, dañino o que viole los derechos de terceros',
          'Intentar eludir filtros de seguridad o generar contenido inapropiado',
          'Compartir tus credenciales de cuenta o permitir que otros usen tu cuenta',
          'Usar la plataforma de manera que pueda dañar, deshabilitar o sobrecargar el servicio',
        ]},
      ]},
      { num: '4', title: 'Aviso sobre el contenido de IA', blocks: [
        { type: 'p', text: 'LearnX-AI usa inteligencia artificial para generar videos educativos, explicaciones y retroalimentación. Aunque nos esforzamos por la precisión:' },
        { type: 'ul', items: [
          'El contenido generado por IA puede contener errores, inexactitudes u omisiones',
          'No se debe confiar en el contenido como única fuente para decisiones críticas',
          'Los profesores son responsables de verificar el contenido generado por IA antes de usarlo en evaluaciones formales',
        ]},
        { type: 'p', text: 'El tutor IA está diseñado para apoyar el aprendizaje, no para reemplazar a profesores cualificados.' },
      ]},
      { num: '5', title: 'Responsabilidades de los profesores', blocks: [
        { type: 'p', text: 'Los profesores que usan LearnX-AI aceptan:' },
        { type: 'ul', items: [
          'Revisar el contenido generado por IA para verificar su precisión antes de presentarlo a los estudiantes',
          'Garantizar el uso apropiado de la plataforma en sus aulas',
          'Gestionar las cuentas de los estudiantes de manera responsable y de acuerdo con la política escolar',
          'No usar los datos de aprendizaje de los estudiantes para fines ajenos al apoyo educativo',
        ]},
      ]},
      { num: '6', title: 'Propiedad intelectual', blocks: [
        { type: 'p', text: 'Todo el contenido, software y tecnología en LearnX-AI — incluyendo modelos de IA, pipelines de generación de video y la interfaz de la plataforma — es propiedad de NordX Labs Oy o sus licenciantes.' },
        { type: 'p', text: 'Los videos y contenidos generados por IA creados con las herramientas de LearnX-AI pueden usarse para fines educativos dentro de la escuela. No puedes revenderlos, sublicenciarlos ni distribuirlos fuera de tu institución educativa sin permiso escrito.' },
        { type: 'p', text: 'Tus propias presentaciones (materiales subidos, contenido de cursos) siguen siendo tu propiedad intelectual.' },
      ]},
      { num: '7', title: 'Privacidad', blocks: [
        { type: 'p', text: 'Tu uso de LearnX-AI también se rige por nuestra Política de privacidad, disponible en learnx-ai.com/privacy. Al usar la plataforma, consientes la recopilación y el tratamiento de datos tal como se describe en la Política de privacidad.' },
      ]},
      { num: '8', title: 'Disponibilidad del servicio', blocks: [
        { type: 'p', text: 'Nos esforzamos por proporcionar un servicio confiable, pero no garantizamos un funcionamiento ininterrumpido o sin errores. Podemos:' },
        { type: 'ul', items: [
          'Realizar mantenimiento programado (con aviso previo cuando sea posible)',
          'Actualizar o modificar las características de la plataforma',
          'Suspender temporalmente el acceso por razones técnicas',
        ]},
        { type: 'p', text: 'No somos responsables de ninguna pérdida o inconveniente causado por la indisponibilidad temporal del servicio.' },
      ]},
      { num: '9', title: 'Limitación de responsabilidad', blocks: [
        { type: 'p', text: 'En la máxima medida permitida por la ley, NordX Labs Oy no es responsable de:' },
        { type: 'ul', items: [
          'Daños indirectos, incidentales o consecuentes',
          'Pérdida de datos, ganancias o resultados educativos derivados del uso o la imposibilidad de usar el servicio',
          'Errores o inexactitudes en el contenido educativo generado por IA',
        ]},
        { type: 'p', text: 'Nuestra responsabilidad total hacia ti por cualquier reclamación derivada del uso del servicio se limita a las tarifas pagadas por tu institución en los 12 meses anteriores a la reclamación.' },
      ]},
      { num: '10', title: 'Rescisión de cuenta', blocks: [
        { type: 'p', text: 'Las cuentas pueden ser rescindidas o suspendidas:' },
        { type: 'ul', items: [
          'Por el usuario en cualquier momento a través de Configuración → Eliminar cuenta',
          'Por los administradores escolares que gestionan cuentas institucionales',
          'Por NordX Labs Oy por incumplimiento de estos términos',
          'Automáticamente cuando finaliza la suscripción de una escuela',
        ]},
        { type: 'p', text: 'Tras la rescisión, tus datos personales serán eliminados de acuerdo con nuestra Política de privacidad.' },
      ]},
      { num: '11', title: 'Ley aplicable', blocks: [
        { type: 'p', text: 'Estos términos se rigen por las leyes de Finlandia. Cualquier disputa se resolverá en el tribunal de distrito de Espoo, Finlandia, a menos que la ley local obligatoria de protección al consumidor lo requiera de otro modo.' },
      ]},
      { num: '12', title: 'Cambios en los términos', blocks: [
        { type: 'p', text: 'Podemos actualizar estos términos de vez en cuando. Te notificaremos sobre cambios importantes a través de la plataforma o por email. El uso continuado del servicio después de la notificación constituye la aceptación de los nuevos términos.' },
      ]},
      { num: '13', title: 'Contacto', blocks: [
        { type: 'table', rows: [['Empresa', 'NordX Labs Oy'], ['Email', 'hello@animlearn.com'], ['ID fiscal', '3615236-4']] },
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

export default function TermsOfServicePage() {
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
          <p className="text-[var(--tx6)] text-sm mb-4">{c.lastUpdated}</p>
          <p className="text-[var(--tx4)] text-sm leading-relaxed border-l-2 border-purple-500/40 pl-4">{c.intro}</p>
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
            <Link href="/privacy" className="text-[var(--tx6)] hover:text-[var(--tx1)] text-xs transition-colors">Privacy Policy</Link>
            <Link href="/terms" className="text-purple-400 text-xs">Terms of Service</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
