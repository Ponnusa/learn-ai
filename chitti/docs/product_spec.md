# Product specification — Companion Robot ("Chitti")

Version 0.1, as supplied by the product owner. Kept verbatim as the source of
truth for every other doc in this folder — if requirements change, update
this file first (bump the version header) and then propagate changes to
`architecture.md`, `risk_register.md`, etc.

---

# PROJECT SPECIFICATION
## Child-Safe AI Companion Robot — Prototype to Commercial Product

**Project codename:** Companion Robot
**Document version:** 0.1
**Status:** Initial engineering specification
**Target market:** Finland first, then EU
**Intended users:** Children under 12, with parent/guardian supervision and controls
**Initial platform:** Raspberry Pi 5
**Deployment strategy:** Local robot controller with pluggable local/cloud AI services
**Primary objective:** Build a functional prototype using an architecture that can evolve into a maintainable, secure and legally compliant commercial device.

---

# 1. Project vision

Develop a friendly physical AI companion that children can speak with naturally. It should support conversation, educational activities, storytelling, jokes, reminders and carefully controlled memory.

The robot must feel responsive and conversational without pretending to be human, encouraging emotional dependency, or silently collecting unnecessary personal information.

The initial deliverable is a working engineering prototype—not a product claimed to be certified. From the beginning, the codebase, hardware documentation, risk controls and data architecture must support future product-safety testing and regulatory assessment.

## Core principles

1. Safety before personality.
2. Natural, interruptible conversation.
3. The robot remains functional and safe if the internet or AI server fails.
4. Parents and children can understand and control what is remembered.
5. The game engine, not the language model, determines educational answers.
6. The robot must never rely on cloud AI to stop a motor or execute a physical emergency stop.
7. No unnecessary recording, profiling or retention of children's data.
8. Every major design decision must be documented.
9. All third-party software, models and hardware must have documented licences and provenance.
10. Do not claim legal compliance or certification until supported by the applicable assessment and evidence.

# 2. Scope

## 2.1 MVP features

The first prototype must support:

- Spoken conversation using a microphone and speaker.
- Wake-word activation or an explicit push-to-talk mode.
- Full-duplex or near-real-time conversation where feasible.
- Interrupting the robot while it is speaking.
- A clear listening indicator and physical microphone mute.
- AI-generated answers, jokes, stories and age-appropriate explanations.
- Basic maths and STEM activities.
- Optional reminders.
- Explicitly controlled, editable and deletable memories.
- A basic parent configuration interface.
- A safe offline/degraded mode.
- Structured logging that excludes raw audio and unnecessary personal data by default.

## 2.2 Out of scope for the first prototype

Do not implement these unless explicitly approved in a later milestone:

- Camera, facial recognition or emotion recognition.
- Voice-based identity recognition of children.
- Autonomous movement around a home.
- Remote motor control through an AI model.
- Advertising, child profiling or personalised marketing.
- Social-media access or unrestricted web browsing by the child.
- Payment features or child accounts with unnecessary personal information.
- Medical, psychological or therapeutic claims.
- Unsupervised external messaging.
- Recording or retaining continuous raw audio.
- A production cloud service exposed publicly without security review.

# 3. Proposed system architecture

Implement independent modules with stable interfaces. Do not place the entire application in one Python script.

## 3.1 Hardware layer

Initial hardware:

- Raspberry Pi 5, preferably 8 GB RAM for development.
- Raspberry Pi-compatible microphone or USB microphone array.
- Speaker with a suitable amplifier.
- Physical microphone mute switch.
- Visible listening/status LED.
- Physical power control and safe shutdown.
- Optional small display or buttons.
- Optional low-power microcontroller for motor control and hardware safety.
- A protected, appropriately rated power supply.
- A documented battery and charging subsystem if a battery is introduced.

All physical components must be replaceable without rewriting the conversation system.

The Raspberry Pi or a dedicated controller must own local hardware safety. AI-generated text or tool calls must never directly control motor PWM, raw GPIO, or emergency-stop functions.

## 3.2 Software components

Implement the following logical services:

**A. Device Controller**
- Hardware abstraction for audio, LEDs, buttons and future motors.
- Device startup and graceful shutdown.
- Watchdog and service-health monitoring.
- Local emergency-stop handling.
- Hardware mute-state enforcement.

**B. Audio Engine**
- Microphone capture.
- Voice activity detection.
- Wake-word or push-to-talk activation.
- Echo cancellation and noise handling where supported.
- Audio playback.
- Barge-in detection.
- Immediate playback cancellation when the user interrupts.
- Explicit audio-buffer limits and lifecycle management.

**C. Voice Interaction Engine**
- Streaming speech input and output.
- Turn-taking and conversation state.
- Support for cancellation of in-flight requests.
- Pluggable speech-to-speech and modular ASR/LLM/TTS backends.
- Timeouts, reconnection and fallback behaviour.

**D. Conversation Service**
- Age-appropriate response policies.
- Conversation context management.
- Tool invocation through a strict allowlist.
- Clear separation between model-generated suggestions and trusted application actions.
- AI identity transparency.
- Safety handling for distress, abuse disclosures and other sensitive conversations.

**E. Memory Service**
- Explicitly approved memory creation.
- Memory review, correction and deletion.
- Expiration and retention policies.
- Separation of durable memories from temporary conversation context.
- Parent-controlled configuration.
- No raw-audio archive by default.

**F. Education Engine**
- Deterministic maths and STEM exercises.
- Answer validation.
- Hints and difficulty levels.
- Learning progress stored only when enabled.
- AI-generated explanations that cannot override the engine's answer key.

**G. Reminder Service**
- Locally scheduled reminders.
- Explicit user or parent confirmation where appropriate.
- Cancellation, editing and expiration.
- No dependence on the LLM to trigger a reminder at the correct time.

**H. Parent Controls**
- Configure network/cloud use.
- Configure memory and retention.
- Inspect and delete saved memories.
- Enable or disable features.
- View device status and relevant privacy information.
- Initiate data export or deletion where supported.
- Apply a parent-controlled usage schedule if required.

**I. Compliance and Diagnostics**
- Versioned configuration.
- Software bill of materials.
- Dependency and model licence inventory.
- Risk register.
- Security event records without unnecessary child data.
- Test reports and architecture decisions.
- Device and firmware version information.

# 4. Voice and conversation requirements

Natural conversation is a core differentiator.

## Required behaviour

- The robot must support short, natural conversational turns.
- The user must be able to interrupt playback.
- When interrupted, playback should stop promptly and the new input should take priority.
- The system must not continue speaking a stale response after the conversation has moved on.
- The audio system must avoid accumulating large buffers that cause conversational delay.
- The system must distinguish listening, processing, speaking, muted and offline states.
- If a cloud request fails, the system must recover gracefully.
- A hardware mute must prevent microphone capture regardless of software or cloud state.

## Performance targets

Treat these as engineering targets to measure—not guaranteed capabilities.

- Target interruption-to-playback-stop latency: below 200 ms under supported operating conditions.
- Target first audible response: approximately one second after the user finishes a short utterance, where the selected model, connection and hardware allow it.
- Measure p50 and p95 latency, not only averages.
- Measure reconnect time, packet loss, speech recognition quality and false wake-ups.
- Test in realistic rooms with background speech and the robot's own speaker playing.

If the target is not achievable with the chosen backend, document the measured result and propose alternatives instead of hiding the limitation.

## Voice architecture

Create a common interface so different implementations can be tested:

- `SpeechToSpeechBackend`
- `SpeechRecognitionBackend`
- `LanguageModelBackend`
- `TextToSpeechBackend`
- `AudioTransport`

Evaluate a real-time speech-to-speech model such as Moshi as one candidate, not as a hard dependency. Also benchmark a modular ASR + LLM + TTS pipeline.

Do not assume a model supports Finnish, low latency, interruption, commercial use or local deployment until each has been verified.

The application must not require a specific cloud provider or model vendor.

# 5. Child safety and interaction policy

The robot is an AI system, not a human, parent, therapist or substitute for trusted people.

## Required behaviour

- Be friendly, calm, respectful and age-appropriate.
- Explain that it is an AI when relevant and never deliberately claim to be a real person.
- Never encourage secrecy from parents or trusted adults.
- Never say that the child must prefer the robot over family or friends.
- Never use guilt, threats, jealousy or emotional pressure to increase engagement.
- Do not reward longer usage or encourage a child to stay awake to keep talking.
- Do not provide sexual content, instructions for dangerous activities or assistance facilitating self-harm.
- Avoid collecting sensitive information about the child or third parties.
- Do not infer or store a child's emotional or medical profile.
- Encourage a trusted adult when a child raises a serious safety concern.
- For urgent danger, use a carefully designed, age-appropriate escalation response. Do not claim that the robot has contacted emergency services unless a verified integration has actually done so.

Safety policy must be enforced in application logic and tested independently of the model's personality prompt.

The model must not have unrestricted access to shell commands, files, network destinations, hardware pins or system configuration.

# 6. Memory and privacy specification

Memory must be optional, understandable and controllable.

## Memory categories

1. **Conversation context:** temporary context needed for the current conversation.
2. **Personal preferences:** optional facts such as favourite topics or preferred difficulty.
3. **Reminders:** explicit tasks with dates, times and expiration.
4. **Learning state:** optional progress in educational activities.
5. **Daily summary:** created only when the feature is enabled and the applicable controls are satisfied.

Do not store every conversation as a permanent memory.

## Memory schema

Use a versioned schema containing fields such as:

- `id`
- `category`
- `content`
- `created_at`
- `updated_at`
- `expires_at`
- `source`
- `consent_or_authorization_status`
- `retention_policy`
- `schema_version`

Use synthetic test data during development. Do not place real children's personal data into development fixtures, issue trackers or source control.

## Privacy requirements

- No raw audio retention by default.
- Do not use children's conversations to train models by default.
- Minimise data sent to cloud providers.
- Document every external service and data recipient.
- Encrypt communications and protect stored data.
- Keep secrets out of source code and logs.
- Provide clear deletion and retention behaviour.
- Avoid retaining sensitive disclosures as durable memory.
- Do not use children's data for advertising.
- Document whether processing occurs locally, in the EU or elsewhere.
- Implement parent-facing controls appropriate to the product and applicable law.

Before any child-facing pilot, document the legal basis, transparency information, access controls, retention schedule and whether a Data Protection Impact Assessment is required. Obtain specialist privacy advice for the proposed processing.

# 7. Education and STEM activities

The education engine must be deterministic and separate from the generative AI.

## First activity

Implement a multiplication practice activity with:

- Configurable difficulty.
- Randomly generated questions within defined bounds.
- Correct-answer validation in code.
- Hints and explanations.
- Retry and skip options.
- Optional progress tracking.
- A safe way to exit the activity.

The AI may explain why an answer is correct or offer a hint. It must not decide whether the submitted answer is correct.

## Reusable activity interface

Implement an interface similar to:

- `start_activity(activity_id, configuration)`
- `submit_answer(activity_session_id, answer)`
- `get_activity_state(activity_session_id)`
- `request_hint(activity_session_id)`
- `end_activity(activity_session_id)`

Return structured data with a documented schema. Validate all model-generated parameters before use.

Later activities may include arithmetic, geometry, logic puzzles, basic physics, programming concepts and science stories.

# 8. Reminder and time-management requirements

Use a trusted scheduler rather than relying on the language model to remember future events.

Each reminder should include:

- Identifier.
- Reminder text.
- Scheduled time and time zone.
- Creation source.
- Expiration or recurrence rules.
- Enabled/disabled status.

Support create, list, edit, dismiss and delete operations.

Confirm ambiguous dates and times. Handle device restarts and daylight-saving changes. Do not create reminders based on an inferred instruction when the user has not actually asked for one.

# 9. Security and system reliability

Implement:

- Least-privilege service accounts.
- Separate development and production configurations.
- Encrypted network communication.
- Authentication for parent controls and remote administration.
- Secure secret management.
- Dependency pinning and vulnerability scanning.
- Signed updates or another appropriately secure update mechanism before commercial deployment.
- Defined support and security-update policy.
- Rate limits and timeouts for external services.
- Network allowlisting for service-to-service communication where practical.
- Protection against prompt injection and malicious content.
- Schema validation for every model-generated tool request.
- Safe failure modes when the network, model or storage is unavailable.

The robot must never execute arbitrary instructions returned by the model.

If cloud access is unavailable, the robot should clearly indicate limited functionality. Local controls, mute, emergency stop and safe shutdown must continue to work.

# 10. Proposed technology stack

Start with technologies that are straightforward to test and replace.

- **Language:** Python for the initial application and orchestration.
- **Device:** Raspberry Pi 5.
- **Audio:** ALSA/PipeWire or another verified Linux audio configuration.
- **Wake word/VAD:** evaluate lightweight, licence-compatible options.
- **Transport:** asynchronous streaming, using WebSocket or another appropriate protocol.
- **AI:** provider-neutral interfaces with selectable local/cloud implementations.
- **Memory:** SQLite for the first local prototype, with migrations and a repository abstraction.
- **Scheduling:** a local scheduler with persistent storage.
- **STEM games:** Pygame or Pygame Zero for an initial display-based activity.
- **Testing:** pytest, integration tests and hardware-in-the-loop tests where available.
- **Configuration:** validated configuration files and environment-based secrets.
- **Packaging:** reproducible installation instructions and pinned dependencies.

Avoid Kubernetes, microservices and complex infrastructure for the first prototype unless a demonstrated requirement justifies them.

# 11. Suggested repository structure

```text
companion-robot/
├── README.md
├── pyproject.toml
├── .env.example
├── docs/
│   ├── product_spec.md
│   ├── architecture.md
│   ├── risk_register.md
│   ├── privacy_data_map.md
│   ├── compliance_plan.md
│   ├── bill_of_materials.md
│   ├── model_and_licence_inventory.md
│   ├── security_threat_model.md
│   └── decisions/
├── config/
│   ├── development.yaml
│   └── example.yaml
├── src/
│   └── companion_robot/
│       ├── app.py
│       ├── config/
│       ├── device/
│       ├── audio/
│       ├── voice/
│       ├── conversation/
│       ├── safety/
│       ├── memory/
│       ├── education/
│       ├── reminders/
│       ├── parent_controls/
│       ├── storage/
│       └── diagnostics/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── safety/
│   └── hardware/
└── scripts/
    ├── setup_dev.sh
    ├── run_local.sh
    └── run_tests.sh
```

Adapt the structure to the existing repository if one exists. Do not move or replace existing code without first understanding it.

# 12. Development milestones

## Milestone 0 — Repository and design assessment

Deliver:
- Existing-code inventory.
- Architecture proposal.
- Hardware assumptions.
- Dependency and licence review.
- Initial threat model.
- Initial risk register.
- List of unresolved decisions.

Do not begin a large rewrite before presenting this assessment.

## Milestone 1 — Local device foundation

Deliver:
- Application starts and shuts down cleanly.
- Microphone and speaker tests.
- Status LED and mute-switch behaviour.
- Configuration validation.
- Structured diagnostics.
- Unit tests and setup instructions.

## Milestone 2 — Voice conversation

Deliver:
- Working voice input and output.
- One selectable AI backend.
- Interruptible playback.
- Timeouts and cancellation.
- Measured latency report.
- Clear offline/error states.

## Milestone 3 — Companion behaviours

Deliver:
- Stories, jokes and general conversation.
- Age-appropriate safety layer.
- Explicit memory creation, review and deletion.
- Persistent reminders.
- Tests for prompt injection and unsafe model output.

## Milestone 4 — STEM activity

Deliver:
- One playable maths activity.
- Deterministic answer checking.
- Hints and explanations.
- Activity tests.
- No direct model control of game logic.

## Milestone 5 — Parent controls and privacy

Deliver:
- Parent-controlled settings.
- Memory review and deletion.
- Cloud/local mode configuration.
- Documented data flow.
- Retention and deletion tests.
- Prototype privacy notice.

## Milestone 6 — Pre-compliance assessment

Deliver:
- Production-intent hardware description.
- Preliminary bill of materials.
- Safety and security risk assessment.
- Supplier documentation inventory.
- Applicable-law and standards assessment with qualified external input.
- Testing laboratory quotation or test plan.
- List of remaining compliance gaps.

## Milestone 7 — Production-intent design

Proceed only after reviewing the pre-compliance findings.

Deliver:
- Design suitable for repeatable manufacturing.
- Hardware and firmware version control.
- Update and support strategy.
- Manufacturing test procedure.
- Final risk-management plan.
- Required conformity documentation and test evidence before market launch.

# 13. Testing and acceptance criteria

A feature is not complete merely because it works once on the developer's machine.

Required tests include:

- Microphone mute physically disables capture.
- Interrupting playback stops the previous response promptly.
- A failed cloud request does not crash the application.
- The device remains safely controllable when offline.
- The model cannot invoke arbitrary commands.
- Model output cannot bypass deterministic maths validation.
- Memory deletion removes the relevant stored record and associated copies under the defined retention design.
- Expired reminders and memories follow their documented policies.
- Logs do not contain raw audio, secrets or unnecessary personal data.
- Unsafe or manipulative responses trigger the appropriate safety behaviour.
- Service restart and power loss do not corrupt persistent state.
- Third-party dependency and model licences are documented.
- Automated tests pass, and manual test results are recorded.

Create regression tests for every serious bug.

# 14. Compliance strategy

Treat regulatory classification as an open task that must be resolved with qualified specialists.

Investigate at least:

- Current EU toy-safety requirements if the product is classified as a toy.
- Applicable EN 71 standards and EN IEC 62115, where relevant.
- Radio Equipment Directive and applicable radio/EMC requirements.
- RoHS and other relevant environmental requirements.
- GDPR and Finnish data-protection requirements.
- Cyber Resilience Act obligations and applicable dates.
- EU AI Act requirements, including transparency obligations.
- Battery, charger, electrical and product-labelling requirements as applicable.
- Consumer protection, product liability, accessibility and language requirements where relevant.

Do not assume every listed standard applies. Determine the correct standards, editions and conformity route for the final product.

The EU Toy Safety Regulation (EU) 2025/2509 is scheduled to apply from 1 August 2030, with certain provisions applying earlier. The AI Act's Article 50 transparency obligations apply from 2 August 2026. Maintain a dated regulatory register and recheck requirements before pilot testing and commercial launch.

Official starting points:
- Toy safety: https://single-market-economy.ec.europa.eu/sectors/toys/toy-safety_en
- Toy Safety Regulation: https://eur-lex.europa.eu/eli/reg/2025/2509/oj
- AI Act transparency: https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act
- Finnish Safety and Chemicals Agency: https://tukes.fi/en
- Finnish Data Protection Ombudsman: https://tietosuoja.fi/en/home

No software architecture or checklist alone establishes compliance. Confirm the actual requirements with the relevant authorities, testing laboratory and legal/privacy specialists.

# 15. Instructions to the coding agent

Act as a senior embedded systems engineer, Python architect and security-conscious product engineer.

When working on this project:

1. Inspect the repository and available hardware before making assumptions.
2. Read existing documentation and preserve working functionality.
3. Present a concise implementation plan before major architectural changes.
4. Implement small, testable increments.
5. Use typed interfaces, clear module boundaries and documented configuration.
6. Write automated tests with each meaningful feature.
7. Prefer maintained libraries with suitable licences.
8. Never hardcode credentials or commit secrets.
9. Do not add real children's personal data to tests.
10. Do not add cameras, facial recognition, cloud recording or unrequested features.
11. Do not let the LLM execute arbitrary code or control hardware directly.
12. Keep physical safety functions independent of the AI.
13. Document uncertainty instead of claiming unsupported functionality.
14. Record significant architecture choices in `docs/decisions/`.
15. Update setup instructions, tests and risk documentation when behaviour changes.
16. Identify which tests were actually run and which require physical hardware.
17. Do not claim certification, legal compliance or production readiness without appropriate evidence.
18. Do not introduce a paid cloud dependency without documenting its cost, privacy implications and alternatives.
19. Keep the model provider replaceable.
20. Ask for approval before introducing a substantial new dependency, external service, data-collection feature or breaking change.

## First task for the coding agent

**Do not immediately implement the entire robot.**

Start with Milestone 0:

1. Inspect the repository and hardware configuration.
2. Summarise the existing implementation.
3. Identify missing components and architectural risks.
4. Propose a minimal implementation plan for Milestone 1.
5. Create or update the initial documentation files.
6. List the assumptions that need my decision.
7. Report the commands and tests used, along with the results.

Wait for approval before beginning a substantial rewrite.

# Definition of success

The prototype is successful when a child can speak naturally with the robot, interrupt it, play a simple educational game, use optional reminders and manage explicitly saved memories through appropriate controls—while the physical device remains safe, privacy-conscious, testable and maintainable.

The commercial design is successful only when the final hardware, software, intended use and data processing have been assessed against the applicable legal requirements and the required conformity evidence has been completed.
