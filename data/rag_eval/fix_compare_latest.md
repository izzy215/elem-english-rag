# /fix 비교 실험 — rag-gemini-real — 2026-09-14T11:56:50 · eval 110문장 · 규칙 100개 · RAG 파이프라인 (검색 상위 5 + 공통 규칙, 임베딩 all-MiniLM-L6-v2) · 프롬프트 fix_fallback.txt

| 문장 | 정답 | local (qwen2.5:32b-instruct) |
|---|---|---|
| I hungry now. | R-01 | ✗ R-36 8692ms |
| Good evening Dad. | R-02 | ✗ 놓침 (ok) 3329ms |
| This is Tom pencil. | R-03 | ✗ 놓침 (ok) 4141ms |
| This is my daughters. | R-04 | ✗ 놓침 (ok) 3821ms |
| There are a book on the desk. | R-05 | ✗ 놓침 (ok) 2947ms |
| She a grade has every day. | R-06 | ✗ 놓침 (ok) 4195ms |
| The bird can runs fast. | R-07 | ✓ 4032ms |
| This birds are amazing. | R-08 | ✓ 3850ms |
| I have many soup. | R-09 | ✓ 4037ms |
| I want to a dessert. | R-10 | ✗ OTHER 2771ms |
| I see leaf a black. | R-11 | ✗ R-38 4164ms |
| I have nine pencil. | R-12 | ✓ 4161ms |
| He was first in line. | R-13 | ✓ 4062ms |
| This is cold today. | R-14 | ✗ 놓침 (ok) 3998ms |
| A storm will hits the coast. | R-15 | ✓ 4215ms |
| Trees bloom on spring. | R-16 | ✓ 4171ms |
| He wear a blue coat now. | R-17 | ✓ 3947ms |
| Ear is cold. | R-18 | ✗ OTHER 2811ms |
| I like dance. | R-19 | ✗ 놓침 (ok) 4085ms |
| I enjoy collect. | R-20 | ✓ 3908ms |
| I have a test in friday. | R-21 | ✓ 4290ms |
| I visit usually my grandparents every month. | R-22 | ✓ 4329ms |
| We go to school by a subway. | R-23 | ✓ 4761ms |
| We go to library every day. | R-24 | ✓ 4283ms |
| She wants to be designer. | R-25 | ✓ 4473ms |
| My uncle is dancer. | R-26 | ✓ 4148ms |
| She is bored for her son. | R-27 | ✗ 놓침 (ok) 4086ms |
| He felt very too nervous to continue. | R-28 | ✓ 4050ms |
| How many is our money? | R-29 | ✓ 4166ms |
| The furniture is on the bedroom. | R-30 | ✗ R-96 4419ms |
| He buy new shoes yesterday. | R-31 | ✗ R-95 4211ms |
| A farmer harvest corn in fall. | R-32 | ✗ R-16 4333ms |
| I have two snack. | R-33 | ✗ R-38 4035ms |
| I have a elephant. | R-34 | ✓ 3879ms |
| He is eat lunch now. | R-35 | ✓ 3845ms |
| She are my cousin. | R-36 | ✓ 3914ms |
| It is cold yesterday. | R-37 | ✗ R-31 3733ms |
| I have pencil. | R-38 | ✓ 3861ms |
| How you are this evening? | R-39 | ✓ 4210ms |
| Great to meet you, also. | R-40 | ✓ 4310ms |
| You welcome, Tom. | R-41 | ✓ 4150ms |
| He has a brother a cousin. | R-42 | ✓ 4449ms |
| Her grandparents is kind. | R-43 | ✓ 4101ms |
| My daughter is nine year old. | R-44 | ✗ OTHER 2960ms |
| You close the door, please. | R-45 | ✓ 4051ms |
| Who homework is this? | R-46 | ✗ 놓침 (ok) 4081ms |
| My bag is at the desk and the window. | R-47 | ✗ R-30 4731ms |
| A bear can not flies. | R-48 | ✓ 16069ms |
| There isn't many creatures in this zoo. | R-49 | ✓ 15470ms |
| A bird is strong than a cat. | R-50 | ✓ 4042ms |
| He would like to a juice. | R-51 | ! 실패 6886ms |
| I don't have some bananas at home. | R-52 | ✗ OTHER 3138ms |
| He drank a milk glass after dinner. | R-53 | ✓ 4696ms |
| He likes purples balloons at the party. | R-54 | ✗ 놓침 (ok) 3750ms |
| What animal you like the best? | R-55 | ✗ OTHER 2900ms |
| That clock looks brownly in this light. | R-56 | ✗ 놓침 (ok) 3118ms |
| How many plate is there in the room? | R-57 | ✗ R-05 4443ms |
| He has one triple the money now. | R-58 | ✓ 3964ms |
| There are hundred of bikes on the highway. | R-59 | ✓ 16810ms |
| How's the weather like today? | R-60 | ✗ OTHER 2942ms |
| It is getting warmly these days. | R-61 | ✗ 놓침 (ok) 3234ms |
| He carries an umbrella because cold. | R-62 | ✓ 4592ms |
| She goes to skate every December. | R-63 | ✗ OTHER 3081ms |
| Fall is coolest season of all. | R-64 | ✓ 4101ms |
| She travels while August every year. | R-65 | ✗ OTHER 3133ms |
| She wears off her gloves at home. | R-66 | ✗ OTHER 3114ms |
| Her pants is dirty. | R-67 | ✓ 4131ms |
| He looks coolly in his new dress. | R-68 | ✗ R-56 4198ms |
| He has backache now. | R-69 | ✓ 4421ms |
| He washes hands before eating. | R-70 | ✓ 4449ms |
| He has white tooths. | R-71 | ✓ 4042ms |
| He plays a baseball after school. | R-72 | ✓ 4272ms |
| Let's biking around the park. | R-73 | ✗ R-63 3478ms |
| They are good at play soccer. | R-74 | ✓ 4432ms |
| He spends time to paint every day. | R-75 | ✓ 4170ms |
| How many often do you paint at home? | R-76 | ✓ 4133ms |
| He is interested at drawing these days. | R-77 | ✓ 4229ms |
| What time it is now? | R-78 | ✓ 3903ms |
| He wakes up on one o'clock every day. | R-79 | ✗ R-78 4520ms |
| Then I do my homework, first I have a snack. | R-80 | ✗ OTHER 3900ms |
| How long take it to school? | R-81 | ✓ 4438ms |
| How you go to the library every day? | R-82 | ✓ 4578ms |
| She gets in the train every morning. | R-83 | ✓ 4266ms |
| The bank is on the zoo in our town. | R-84 | ✓ 4878ms |
| Where the landmark is in this town? | R-85 | ✓ 4319ms |
| There are a lot bananas on this street. | R-86 | ✗ 놓침 (ok) 3226ms |
| He works a library as a teacher. | R-87 | ✓ 4385ms |
| What does he works? | R-88 | ✗ OTHER 2905ms |
| He would like be a designer someday. | R-89 | ✓ 4647ms |
| The game makes him to embarrassed every time. | R-90 | ✗ OTHER 8010ms |
| He is so much excited after the race. | R-91 | ✓ 8897ms |
| Why she is excited today? | R-92 | ✗ 놓침 (ok) 7845ms |
| It's eight dollar for this cap. | R-93 | ✓ 8687ms |
| I have this fork, please? | R-94 | ✓ 8702ms |
| He buyed a car his sister yesterday. | R-95 | ✗ OTHER 3374ms |
| She studies at her bedroom every evening. | R-96 | ✓ 4238ms |
| Her house is four bedrooms and a big garage. | R-97 | ✓ 4052ms |
| This bathroom is there, near the window. | R-98 | ✗ R-84 4072ms |
| He don't likes rainy days. | R-99 | ✓ 4049ms |
| Do they plays chess well? | R-100 | ✗ R-99 4029ms |
| Hi, Ben! | 정상 | ✓ 정상 유지 3238ms |
| Good morning, everyone! | 정상 | ✓ 정상 유지 3350ms |
| This is my dad. | 정상 | ✓ 정상 유지 3471ms |
| These are my cousins. | 정상 | ✓ 정상 유지 3316ms |
| I have a pencil. | 정상 | ✓ 정상 유지 3433ms |
| There is a cup on the table. | 정상 | ✓ 정상 유지 3455ms |
| Dogs can swim well. | 정상 | ✓ 정상 유지 3487ms |
| I have an apple. | 정상 | ✓ 정상 유지 3436ms |
| I want some water. | 정상 | ✓ 정상 유지 3307ms |
| I see a blue bird. | 정상 | ✓ 정상 유지 3405ms |
| **규칙 적중** | | **58/100** |
| **정상 문장 유지** | | 10/10 |
| **평균 응답** | | 4509ms |

판정: ✓ 정답 규칙 · ✗ R-xx 다른 규칙 · ✗ 놓침(ok) · ✓ 정상 유지 · ✗ 오교정 · ! 실패(호출 오류)
고친 문장 등 원본 응답은 같은 이름의 .json 참고.
