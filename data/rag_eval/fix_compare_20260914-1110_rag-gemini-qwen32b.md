# /fix 비교 실험 — rag-gemini-qwen32b — 2026-09-14T11:10:22 · eval 110문장 · 규칙 100개 · RAG 파이프라인 (검색 상위 5 + 공통 규칙, 임베딩 all-MiniLM-L6-v2) · 프롬프트 fix_fallback.txt

| 문장 | 정답 | local (qwen2.5:32b-instruct) |
|---|---|---|
| I hungry now. | R-01 | ✗ R-36 11885ms |
| Good evening Dad. | R-02 | ✗ 놓침 (ok) 6759ms |
| This is Tom pencil. | R-03 | ✗ 놓침 (ok) 8587ms |
| This is my daughters. | R-04 | ✗ 놓침 (ok) 8589ms |
| There are a book on the desk. | R-05 | ✗ 놓침 (ok) 20648ms |
| She a grade has every day. | R-06 | ✗ 놓침 (ok) 21358ms |
| The bird can runs fast. | R-07 | ✓ 8408ms |
| This birds are amazing. | R-08 | ✓ 8405ms |
| I have many soup. | R-09 | ✓ 8534ms |
| I want to a dessert. | R-10 | ✗ OTHER 7525ms |
| I see leaf a black. | R-11 | ✗ 놓침 (ok) 8741ms |
| I have nine pencil. | R-12 | ✓ 8296ms |
| He was first in line. | R-13 | ✓ 8437ms |
| This is cold today. | R-14 | ✗ 놓침 (ok) 8346ms |
| A storm will hits the coast. | R-15 | ✓ 8882ms |
| Trees bloom on spring. | R-16 | ✓ 21635ms |
| He wear a blue coat now. | R-17 | ✓ 8634ms |
| Ear is cold. | R-18 | ✗ OTHER 7945ms |
| I like dance. | R-19 | ✗ 놓침 (ok) 8827ms |
| I enjoy collect. | R-20 | ✓ 8583ms |
| I have a test in friday. | R-21 | ✓ 8882ms |
| I visit usually my grandparents every month. | R-22 | ✓ 22367ms |
| We go to school by a subway. | R-23 | ✓ 16614ms |
| We go to library every day. | R-24 | ✓ 8703ms |
| She wants to be designer. | R-25 | ✓ 9045ms |
| My uncle is dancer. | R-26 | ✓ 8444ms |
| She is bored for her son. | R-27 | ✗ 놓침 (ok) 8574ms |
| He felt very too nervous to continue. | R-28 | ✓ 8329ms |
| How many is our money? | R-29 | ✓ 8678ms |
| The furniture is on the bedroom. | R-30 | ✗ R-96 9075ms |
| He buy new shoes yesterday. | R-31 | ✗ R-95 8555ms |
| A farmer harvest corn in fall. | R-32 | ✗ R-16 13245ms |
| I have two snack. | R-33 | ✗ R-38 13222ms |
| I have a elephant. | R-34 | ✓ 12670ms |
| He is eat lunch now. | R-35 | ✓ 8398ms |
| She are my cousin. | R-36 | ✓ 8845ms |
| It is cold yesterday. | R-37 | ✗ R-31 8485ms |
| I have pencil. | R-38 | ✓ 8002ms |
| How you are this evening? | R-39 | ✓ 12973ms |
| Great to meet you, also. | R-40 | ✓ 14130ms |
| You welcome, Tom. | R-41 | ✓ 13006ms |
| He has a brother a cousin. | R-42 | ✓ 8943ms |
| Her grandparents is kind. | R-43 | ✓ 9036ms |
| My daughter is nine year old. | R-44 | ✗ OTHER 8184ms |
| You close the door, please. | R-45 | ✓ 8855ms |
| Who homework is this? | R-46 | ✗ 놓침 (ok) 9010ms |
| My bag is at the desk and the window. | R-47 | ✗ R-30 13799ms |
| A bear can not flies. | R-48 | ✓ 8515ms |
| There isn't many creatures in this zoo. | R-49 | ✓ 13084ms |
| A bird is strong than a cat. | R-50 | ✓ 9036ms |
| He would like to a juice. | R-51 | ! 실패 16828ms |
| I don't have some bananas at home. | R-52 | ✗ OTHER 8573ms |
| He drank a milk glass after dinner. | R-53 | ✓ 9058ms |
| He likes purples balloons at the party. | R-54 | ✗ 놓침 (ok) 8791ms |
| What animal you like the best? | R-55 | ✗ R-100 8147ms |
| That clock looks brownly in this light. | R-56 | ✓ 8299ms |
| How many plate is there in the room? | R-57 | ✗ R-05 8751ms |
| He has one triple the money now. | R-58 | ✓ 9148ms |
| There are hundred of bikes on the highway. | R-59 | ✓ 9355ms |
| How's the weather like today? | R-60 | ✗ OTHER 8026ms |
| It is getting warmly these days. | R-61 | ✓ 9337ms |
| He carries an umbrella because cold. | R-62 | ✓ 9204ms |
| She goes to skate every December. | R-63 | ✗ OTHER 8131ms |
| Fall is coolest season of all. | R-64 | ✓ 8716ms |
| She travels while August every year. | R-65 | ✗ OTHER 8899ms |
| She wears off her gloves at home. | R-66 | ✗ OTHER 14499ms |
| Her pants is dirty. | R-67 | ✓ 12068ms |
| He looks coolly in his new dress. | R-68 | ✗ R-56 15528ms |
| He has backache now. | R-69 | ✓ 20455ms |
| He washes hands before eating. | R-70 | ✓ 13979ms |
| He has white tooths. | R-71 | ✓ 12339ms |
| He plays a baseball after school. | R-72 | ✓ 14664ms |
| Let's biking around the park. | R-73 | ✗ R-63 12569ms |
| They are good at play soccer. | R-74 | ✓ 13068ms |
| He spends time to paint every day. | R-75 | ✓ 13053ms |
| How many often do you paint at home? | R-76 | ✓ 12120ms |
| He is interested at drawing these days. | R-77 | ✓ 13504ms |
| What time it is now? | R-78 | ✓ 7527ms |
| He wakes up on one o'clock every day. | R-79 | ✓ 7959ms |
| Then I do my homework, first I have a snack. | R-80 | ✗ OTHER 8137ms |
| How long take it to school? | R-81 | ✓ 8178ms |
| How you go to the library every day? | R-82 | ✓ 8222ms |
| She gets in the train every morning. | R-83 | ✓ 8024ms |
| The bank is on the zoo in our town. | R-84 | ✓ 8756ms |
| Where the landmark is in this town? | R-85 | ✓ 7866ms |
| There are a lot bananas on this street. | R-86 | ✗ 놓침 (ok) 7664ms |
| He works a library as a teacher. | R-87 | ✓ 8066ms |
| What does he works? | R-88 | ✗ OTHER 2887ms |
| He would like be a designer someday. | R-89 | ✓ 4621ms |
| The game makes him to embarrassed every time. | R-90 | ✗ OTHER 3294ms |
| He is so much excited after the race. | R-91 | ✓ 4585ms |
| Why she is excited today? | R-92 | ✓ 2982ms |
| It's eight dollar for this cap. | R-93 | ✓ 4264ms |
| I have this fork, please? | R-94 | ✓ 4403ms |
| He buyed a car his sister yesterday. | R-95 | ✗ OTHER 3360ms |
| She studies at her bedroom every evening. | R-96 | ✓ 4190ms |
| Her house is four bedrooms and a big garage. | R-97 | ✓ 3981ms |
| This bathroom is there, near the window. | R-98 | ✗ R-84 4047ms |
| He don't likes rainy days. | R-99 | ✓ 4439ms |
| Do they plays chess well? | R-100 | ✓ 4317ms |
| Hi, Ben! | 정상 | ✓ 정상 유지 3152ms |
| Good morning, everyone! | 정상 | ✓ 정상 유지 3304ms |
| This is my dad. | 정상 | ✓ 정상 유지 14307ms |
| These are my cousins. | 정상 | ✓ 정상 유지 3332ms |
| I have a pencil. | 정상 | ✓ 정상 유지 3454ms |
| There is a cup on the table. | 정상 | ✓ 정상 유지 3434ms |
| Dogs can swim well. | 정상 | ✓ 정상 유지 3504ms |
| I have an apple. | 정상 | ✓ 정상 유지 3447ms |
| I want some water. | 정상 | ✓ 정상 유지 3295ms |
| I see a blue bird. | 정상 | ✓ 정상 유지 3404ms |
| **규칙 적중** | | **63/100** |
| **정상 문장 유지** | | 10/10 |
| **평균 응답** | | 9123ms |

판정: ✓ 정답 규칙 · ✗ R-xx 다른 규칙 · ✗ 놓침(ok) · ✓ 정상 유지 · ✗ 오교정 · ! 실패(호출 오류)
고친 문장 등 원본 응답은 같은 이름의 .json 참고.
