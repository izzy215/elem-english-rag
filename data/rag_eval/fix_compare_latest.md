# /fix 비교 실험 — rag-gemini-k20-v56059a6 — 2026-09-15T11:31:45 · eval 110문장 · 규칙 100개 · RAG 파이프라인 (검색 상위 20 + 공통 규칙, 임베딩 gemini-embedding-001) · 프롬프트 fix_fallback.txt

| 문장 | 정답 | local (qwen2.5:32b-instruct) |
|---|---|---|
| I hungry now. | R-01 | ✓ 4449ms |
| Good evening Dad. | R-02 | ✗ 놓침 (ok) 3771ms |
| This is Tom pencil. | R-03 | ✗ 놓침 (ok) 4680ms |
| This is my daughters. | R-04 | ✗ R-33 2966ms |
| There are a book on the desk. | R-05 | ✓ 4447ms |
| She a grade has every day. | R-06 | ✗ 놓침 (ok) 4433ms |
| The bird can runs fast. | R-07 | ✓ 4216ms |
| This birds are amazing. | R-08 | ✓ 4308ms |
| I have many soup. | R-09 | ✓ 4410ms |
| I want to a dessert. | R-10 | ✓ 4742ms |
| I see leaf a black. | R-11 | ✗ R-35 4480ms |
| I have nine pencil. | R-12 | ✓ 4637ms |
| He was first in line. | R-13 | ✓ 4743ms |
| This is cold today. | R-14 | ✗ 놓침 (ok) 4545ms |
| A storm will hits the coast. | R-15 | ✓ 4635ms |
| Trees bloom on spring. | R-16 | ✓ 4597ms |
| He wear a blue coat now. | R-17 | ✓ 4403ms |
| Ear is cold. | R-18 | ✗ OTHER 2825ms |
| I like dance. | R-19 | ✗ 놓침 (ok) 4752ms |
| I enjoy collect. | R-20 | ✓ 4312ms |
| I have a test in friday. | R-21 | ✓ 4913ms |
| I visit usually my grandparents every month. | R-22 | ✓ 5090ms |
| We go to school by a subway. | R-23 | ✓ 5216ms |
| We go to library every day. | R-24 | ✓ 4810ms |
| She wants to be designer. | R-25 | ✓ 4796ms |
| My uncle is dancer. | R-26 | ✓ 4812ms |
| She is bored for her son. | R-27 | ✗ R-01 4975ms |
| He felt very too nervous to continue. | R-28 | ✓ 5130ms |
| How many is our money? | R-29 | ✓ 5171ms |
| The furniture is on the bedroom. | R-30 | ✗ R-96 4611ms |
| He buy new shoes yesterday. | R-31 | ✓ 4659ms |
| A farmer harvest corn in fall. | R-32 | ✗ R-16 4612ms |
| I have two snack. | R-33 | ✗ 놓침 (ok) 2732ms |
| I have a elephant. | R-34 | ✓ 4490ms |
| He is eat lunch now. | R-35 | ✓ 4300ms |
| She are my cousin. | R-36 | ✓ 4339ms |
| It is cold yesterday. | R-37 | ✗ R-31 4250ms |
| I have pencil. | R-38 | ✓ 4333ms |
| How you are this evening? | R-39 | ✓ 4697ms |
| Great to meet you, also. | R-40 | ✓ 4673ms |
| You welcome, Tom. | R-41 | ✓ 4686ms |
| He has a brother a cousin. | R-42 | ✓ 4736ms |
| Her grandparents is kind. | R-43 | ✓ 4599ms |
| My daughter is nine year old. | R-44 | ✗ OTHER 3010ms |
| You close the door, please. | R-45 | ✓ 4607ms |
| Who homework is this? | R-46 | ✗ 놓침 (ok) 4676ms |
| My bag is at the desk and the window. | R-47 | ✗ R-30 4716ms |
| A bear can not flies. | R-48 | ✗ R-07 4593ms |
| There isn't many creatures in this zoo. | R-49 | ✓ 4759ms |
| A bird is strong than a cat. | R-50 | ✓ 4898ms |
| He would like to a juice. | R-51 | ✗ OTHER 2856ms |
| I don't have some bananas at home. | R-52 | ✗ OTHER 2915ms |
| He drank a milk glass after dinner. | R-53 | ✓ 5055ms |
| He likes purples balloons at the party. | R-54 | ✓ 4694ms |
| What animal you like the best? | R-55 | ✓ 4460ms |
| That clock looks brownly in this light. | R-56 | ✓ 4945ms |
| How many plate is there in the room? | R-57 | ✓ 4798ms |
| He has one triple the money now. | R-58 | ✓ 4798ms |
| There are hundred of bikes on the highway. | R-59 | ✓ 4756ms |
| How's the weather like today? | R-60 | ✗ OTHER 2967ms |
| It is getting warmly these days. | R-61 | ✓ 4908ms |
| He carries an umbrella because cold. | R-62 | ✓ 5059ms |
| She goes to skate every December. | R-63 | ✓ 5018ms |
| Fall is coolest season of all. | R-64 | ✓ 4870ms |
| She travels while August every year. | R-65 | ✗ OTHER 3124ms |
| She wears off her gloves at home. | R-66 | ✗ OTHER 3177ms |
| Her pants is dirty. | R-67 | ✓ 4556ms |
| He looks coolly in his new dress. | R-68 | ✗ R-56 4641ms |
| He has backache now. | R-69 | ✓ 5030ms |
| He washes hands before eating. | R-70 | ✓ 5030ms |
| He has white tooths. | R-71 | ✓ 4474ms |
| He plays a baseball after school. | R-72 | ✓ 4654ms |
| Let's biking around the park. | R-73 | ✗ 놓침 (ok) 3462ms |
| They are good at play soccer. | R-74 | ✓ 4982ms |
| He spends time to paint every day. | R-75 | ✓ 4720ms |
| How many often do you paint at home? | R-76 | ✓ 4793ms |
| He is interested at drawing these days. | R-77 | ✓ 4725ms |
| What time it is now? | R-78 | ✓ 4378ms |
| He wakes up on one o'clock every day. | R-79 | ✓ 4621ms |
| Then I do my homework, first I have a snack. | R-80 | ✗ OTHER 3877ms |
| How long take it to school? | R-81 | ✓ 5004ms |
| How you go to the library every day? | R-82 | ✓ 4944ms |
| She gets in the train every morning. | R-83 | ✓ 4691ms |
| The bank is on the zoo in our town. | R-84 | ✓ 5435ms |
| Where the landmark is in this town? | R-85 | ✗ OTHER 3592ms |
| There are a lot bananas on this street. | R-86 | ✓ 5199ms |
| He works a library as a teacher. | R-87 | ✓ 4921ms |
| What does he works? | R-88 | ✓ 4659ms |
| He would like be a designer someday. | R-89 | ✓ 4837ms |
| The game makes him to embarrassed every time. | R-90 | ✓ 5227ms |
| He is so much excited after the race. | R-91 | ✓ 5092ms |
| Why she is excited today? | R-92 | ✓ 4569ms |
| It's eight dollar for this cap. | R-93 | ✓ 4799ms |
| I have this fork, please? | R-94 | ✗ OTHER 3475ms |
| He buyed a car his sister yesterday. | R-95 | ✗ OTHER 3246ms |
| She studies at her bedroom every evening. | R-96 | ✓ 4590ms |
| Her house is four bedrooms and a big garage. | R-97 | ✓ 4638ms |
| This bathroom is there, near the window. | R-98 | ✗ R-84 4610ms |
| He don't likes rainy days. | R-99 | ✓ 5172ms |
| Do they plays chess well? | R-100 | ✗ R-99 4972ms |
| Hi, Ben! | 정상 | ✓ 정상 유지 3706ms |
| Good morning, everyone! | 정상 | ✓ 정상 유지 3760ms |
| This is my dad. | 정상 | ✓ 정상 유지 3880ms |
| These are my cousins. | 정상 | ✓ 정상 유지 3875ms |
| I have a pencil. | 정상 | ✓ 정상 유지 3902ms |
| There is a cup on the table. | 정상 | ✓ 정상 유지 4077ms |
| Dogs can swim well. | 정상 | ✓ 정상 유지 4026ms |
| I have an apple. | 정상 | ✓ 정상 유지 3966ms |
| I want some water. | 정상 | ✓ 정상 유지 4061ms |
| I see a blue bird. | 정상 | ✓ 정상 유지 3840ms |
| **규칙 적중** | | **70/100** |
| **정상 문장 유지** | | 10/10 |
| **평균 응답** | | 4448ms |

판정: ✓ 정답 규칙 · ✗ R-xx 다른 규칙 · ✗ 놓침(ok) · ✓ 정상 유지 · ✗ 오교정 · ! 실패(호출 오류)
고친 문장 등 원본 응답은 같은 이름의 .json 참고.
