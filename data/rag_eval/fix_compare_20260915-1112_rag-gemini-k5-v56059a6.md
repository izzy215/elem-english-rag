# /fix 비교 실험 — rag-gemini-k5-v56059a6 — 2026-09-15T11:12:53 · eval 110문장 · 규칙 100개 · RAG 파이프라인 (검색 상위 5 + 공통 규칙, 임베딩 gemini-embedding-001) · 프롬프트 fix_fallback.txt

| 문장 | 정답 | local (qwen2.5:32b-instruct) |
|---|---|---|
| I hungry now. | R-01 | ✗ R-36 7406ms |
| Good evening Dad. | R-02 | ✗ 놓침 (ok) 7870ms |
| This is Tom pencil. | R-03 | ✗ 놓침 (ok) 8695ms |
| This is my daughters. | R-04 | ✗ 놓침 (ok) 8705ms |
| There are a book on the desk. | R-05 | ✓ 8815ms |
| She a grade has every day. | R-06 | ✗ 놓침 (ok) 8542ms |
| The bird can runs fast. | R-07 | ✓ 8252ms |
| This birds are amazing. | R-08 | ✓ 8307ms |
| I have many soup. | R-09 | ✓ 8883ms |
| I want to a dessert. | R-10 | ✗ OTHER 8514ms |
| I see leaf a black. | R-11 | ✗ R-38 8829ms |
| I have nine pencil. | R-12 | ✓ 8520ms |
| He was first in line. | R-13 | ✓ 8606ms |
| This is cold today. | R-14 | ✗ 놓침 (ok) 8586ms |
| A storm will hits the coast. | R-15 | ✓ 8785ms |
| Trees bloom on spring. | R-16 | ✓ 8732ms |
| He wear a blue coat now. | R-17 | ✓ 8409ms |
| Ear is cold. | R-18 | ✗ OTHER 8254ms |
| I like dance. | R-19 | ✗ 놓침 (ok) 8437ms |
| I enjoy collect. | R-20 | ✓ 8709ms |
| I have a test in friday. | R-21 | ✓ 8767ms |
| I visit usually my grandparents every month. | R-22 | ✓ 9219ms |
| We go to school by a subway. | R-23 | ✓ 9262ms |
| We go to library every day. | R-24 | ✓ 7889ms |
| She wants to be designer. | R-25 | ✓ 8789ms |
| My uncle is dancer. | R-26 | ✓ 8884ms |
| She is bored for her son. | R-27 | ✗ R-95 8860ms |
| He felt very too nervous to continue. | R-28 | ✓ 8690ms |
| How many is our money? | R-29 | ✓ 8546ms |
| The furniture is on the bedroom. | R-30 | ✗ R-96 8510ms |
| He buy new shoes yesterday. | R-31 | ✗ R-95 8830ms |
| A farmer harvest corn in fall. | R-32 | ✗ R-16 9093ms |
| I have two snack. | R-33 | ✓ 8768ms |
| I have a elephant. | R-34 | ✓ 8164ms |
| He is eat lunch now. | R-35 | ✓ 8320ms |
| She are my cousin. | R-36 | ✓ 8430ms |
| It is cold yesterday. | R-37 | ✗ R-31 8125ms |
| I have pencil. | R-38 | ✓ 8091ms |
| How you are this evening? | R-39 | ✓ 9149ms |
| Great to meet you, also. | R-40 | ✓ 8711ms |
| You welcome, Tom. | R-41 | ✓ 9040ms |
| He has a brother a cousin. | R-42 | ✓ 9035ms |
| Her grandparents is kind. | R-43 | ✓ 8879ms |
| My daughter is nine year old. | R-44 | ✗ OTHER 7653ms |
| You close the door, please. | R-45 | ✗ OTHER 8205ms |
| Who homework is this? | R-46 | ✗ 놓침 (ok) 7551ms |
| My bag is at the desk and the window. | R-47 | ✗ R-30 8432ms |
| A bear can not flies. | R-48 | ✗ R-07 7531ms |
| There isn't many creatures in this zoo. | R-49 | ✓ 7868ms |
| A bird is strong than a cat. | R-50 | ✓ 8162ms |
| He would like to a juice. | R-51 | ✗ R-89 7932ms |
| I don't have some bananas at home. | R-52 | ✗ OTHER 7530ms |
| He drank a milk glass after dinner. | R-53 | ✓ 7996ms |
| He likes purples balloons at the party. | R-54 | ✓ 7838ms |
| What animal you like the best? | R-55 | ✓ 7600ms |
| That clock looks brownly in this light. | R-56 | ✓ 7703ms |
| How many plate is there in the room? | R-57 | ✓ 7870ms |
| He has one triple the money now. | R-58 | ✓ 8412ms |
| There are hundred of bikes on the highway. | R-59 | ✓ 8350ms |
| How's the weather like today? | R-60 | ✗ OTHER 7504ms |
| It is getting warmly these days. | R-61 | ✓ 7960ms |
| He carries an umbrella because cold. | R-62 | ✓ 8123ms |
| She goes to skate every December. | R-63 | ✓ 4400ms |
| Fall is coolest season of all. | R-64 | ✓ 4183ms |
| She travels while August every year. | R-65 | ✗ OTHER 3131ms |
| She wears off her gloves at home. | R-66 | ✗ OTHER 7951ms |
| Her pants is dirty. | R-67 | ✓ 8789ms |
| He looks coolly in his new dress. | R-68 | ✗ R-56 8257ms |
| He has backache now. | R-69 | ✓ 4248ms |
| He washes hands before eating. | R-70 | ✓ 8731ms |
| He has white tooths. | R-71 | ✓ 3828ms |
| He plays a baseball after school. | R-72 | ✓ 8801ms |
| Let's biking around the park. | R-73 | ! 실패 17813ms |
| They are good at play soccer. | R-74 | ✓ 4104ms |
| He spends time to paint every day. | R-75 | ✓ 8540ms |
| How many often do you paint at home? | R-76 | ✓ 8232ms |
| He is interested at drawing these days. | R-77 | ✓ 7182ms |
| What time it is now? | R-78 | ✓ 7889ms |
| He wakes up on one o'clock every day. | R-79 | ✓ 8344ms |
| Then I do my homework, first I have a snack. | R-80 | ✗ OTHER 9037ms |
| How long take it to school? | R-81 | ✓ 4219ms |
| How you go to the library every day? | R-82 | ✓ 9051ms |
| She gets in the train every morning. | R-83 | ✓ 8384ms |
| The bank is on the zoo in our town. | R-84 | ✓ 8757ms |
| Where the landmark is in this town? | R-85 | ✗ OTHER 8316ms |
| There are a lot bananas on this street. | R-86 | ✓ 8790ms |
| He works a library as a teacher. | R-87 | ✓ 8430ms |
| What does he works? | R-88 | ✗ R-100 8204ms |
| He would like be a designer someday. | R-89 | ✓ 8406ms |
| The game makes him to embarrassed every time. | R-90 | ✗ OTHER 8735ms |
| He is so much excited after the race. | R-91 | ✓ 9008ms |
| Why she is excited today? | R-92 | ✗ R-100 8266ms |
| It's eight dollar for this cap. | R-93 | ✓ 4009ms |
| I have this fork, please? | R-94 | ✓ 8542ms |
| He buyed a car his sister yesterday. | R-95 | ✗ OTHER 8149ms |
| She studies at her bedroom every evening. | R-96 | ✓ 8044ms |
| Her house is four bedrooms and a big garage. | R-97 | ✓ 8264ms |
| This bathroom is there, near the window. | R-98 | ✗ R-84 8333ms |
| He don't likes rainy days. | R-99 | ✓ 4258ms |
| Do they plays chess well? | R-100 | ✓ 8553ms |
| Hi, Ben! | 정상 | ✓ 정상 유지 7159ms |
| Good morning, everyone! | 정상 | ✓ 정상 유지 7243ms |
| This is my dad. | 정상 | ✓ 정상 유지 7324ms |
| These are my cousins. | 정상 | ✓ 정상 유지 7500ms |
| I have a pencil. | 정상 | ✓ 정상 유지 7405ms |
| There is a cup on the table. | 정상 | ✓ 정상 유지 3283ms |
| Dogs can swim well. | 정상 | ✓ 정상 유지 7367ms |
| I have an apple. | 정상 | ✓ 정상 유지 6440ms |
| I want some water. | 정상 | ✓ 정상 유지 7249ms |
| I see a blue bird. | 정상 | ✓ 정상 유지 7235ms |
| **규칙 적중** | | **66/100** |
| **정상 문장 유지** | | 10/10 |
| **평균 응답** | | 7896ms |

판정: ✓ 정답 규칙 · ✗ R-xx 다른 규칙 · ✗ 놓침(ok) · ✓ 정상 유지 · ✗ 오교정 · ! 실패(호출 오류)
고친 문장 등 원본 응답은 같은 이름의 .json 참고.
