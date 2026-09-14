# /fix 비교 실험 — norag-qwen2-5-32b-instruct — 2026-09-14T11:36:42 · eval 110문장 · 규칙 100개 · 규칙 전부 (검색 없음) · 프롬프트 fix_fallback.txt

| 문장 | 정답 | local (qwen2.5:32b-instruct) |
|---|---|---|
| I hungry now. | R-01 | ✓ 6141ms |
| Good evening Dad. | R-02 | ✗ 놓침 (ok) 2428ms |
| This is Tom pencil. | R-03 | ✓ 3213ms |
| This is my daughters. | R-04 | ✗ R-03 3457ms |
| There are a book on the desk. | R-05 | ✓ 3299ms |
| She a grade has every day. | R-06 | ✓ 17561ms |
| The bird can runs fast. | R-07 | ✓ 16730ms |
| This birds are amazing. | R-08 | ✓ 3466ms |
| I have many soup. | R-09 | ✓ 3214ms |
| I want to a dessert. | R-10 | ✓ 3071ms |
| I see leaf a black. | R-11 | ✗ R-06 3254ms |
| I have nine pencil. | R-12 | ✗ R-38 3330ms |
| He was first in line. | R-13 | ✓ 3271ms |
| This is cold today. | R-14 | ✓ 3408ms |
| A storm will hits the coast. | R-15 | ✓ 3579ms |
| Trees bloom on spring. | R-16 | ✓ 3235ms |
| He wear a blue coat now. | R-17 | ✓ 3402ms |
| Ear is cold. | R-18 | ✗ R-14 3151ms |
| I like dance. | R-19 | ✓ 3109ms |
| I enjoy collect. | R-20 | ✓ 3038ms |
| I have a test in friday. | R-21 | ✓ 3522ms |
| I visit usually my grandparents every month. | R-22 | ✓ 3374ms |
| We go to school by a subway. | R-23 | ✓ 3498ms |
| We go to library every day. | R-24 | ✓ 3543ms |
| She wants to be designer. | R-25 | ✓ 3278ms |
| My uncle is dancer. | R-26 | ✓ 3536ms |
| She is bored for her son. | R-27 | ✓ 3905ms |
| He felt very too nervous to continue. | R-28 | ✓ 3616ms |
| How many is our money? | R-29 | ✓ 3259ms |
| The furniture is on the bedroom. | R-30 | ✗ R-03 3523ms |
| He buy new shoes yesterday. | R-31 | ✓ 3287ms |
| A farmer harvest corn in fall. | R-32 | ✗ R-16 3315ms |
| I have two snack. | R-33 | ✗ R-38 3339ms |
| I have a elephant. | R-34 | ✗ R-44 3116ms |
| He is eat lunch now. | R-35 | ✗ R-31 3441ms |
| She are my cousin. | R-36 | ✓ 3290ms |
| It is cold yesterday. | R-37 | ✗ R-07 16173ms |
| I have pencil. | R-38 | ✓ 16487ms |
| How you are this evening? | R-39 | ✗ R-49 15620ms |
| Great to meet you, also. | R-40 | ✓ 16454ms |
| You welcome, Tom. | R-41 | ✓ 16102ms |
| He has a brother a cousin. | R-42 | ✓ 16670ms |
| Her grandparents is kind. | R-43 | ✓ 16563ms |
| My daughter is nine year old. | R-44 | ✓ 16144ms |
| You close the door, please. | R-45 | ✓ 16781ms |
| Who homework is this? | R-46 | ✓ 16793ms |
| My bag is at the desk and the window. | R-47 | ✓ 16251ms |
| A bear can not flies. | R-48 | ✗ R-07 16216ms |
| There isn't many creatures in this zoo. | R-49 | ✓ 16454ms |
| A bird is strong than a cat. | R-50 | ✓ 16670ms |
| He would like to a juice. | R-51 | ✓ 16345ms |
| I don't have some bananas at home. | R-52 | ✓ 16430ms |
| He drank a milk glass after dinner. | R-53 | ✗ R-23 17019ms |
| He likes purples balloons at the party. | R-54 | ✓ 16546ms |
| What animal you like the best? | R-55 | ✗ ?R-046 16626ms |
| That clock looks brownly in this light. | R-56 | ✗ R-66 16893ms |
| How many plate is there in the room? | R-57 | ✗ R-09 16664ms |
| He has one triple the money now. | R-58 | ✓ 17557ms |
| There are hundred of bikes on the highway. | R-59 | ✓ 16557ms |
| How's the weather like today? | R-60 | ✓ 16666ms |
| It is getting warmly these days. | R-61 | ✓ 16714ms |
| He carries an umbrella because cold. | R-62 | ✓ 17134ms |
| She goes to skate every December. | R-63 | ✗ R-31 16339ms |
| Fall is coolest season of all. | R-64 | ✓ 16238ms |
| She travels while August every year. | R-65 | ✓ 16271ms |
| She wears off her gloves at home. | R-66 | ✓ 17014ms |
| Her pants is dirty. | R-67 | ✓ 15895ms |
| He looks coolly in his new dress. | R-68 | ✓ 16682ms |
| He has backache now. | R-69 | ✓ 16748ms |
| He washes hands before eating. | R-70 | ✓ 17223ms |
| He has white tooths. | R-71 | ✓ 16764ms |
| He plays a baseball after school. | R-72 | ✗ R-22 16703ms |
| Let's biking around the park. | R-73 | ✓ 16644ms |
| They are good at play soccer. | R-74 | ✓ 16679ms |
| He spends time to paint every day. | R-75 | ✓ 17113ms |
| How many often do you paint at home? | R-76 | ✓ 16942ms |
| He is interested at drawing these days. | R-77 | ✓ 16585ms |
| What time it is now? | R-78 | ✗ R-88 16658ms |
| He wakes up on one o'clock every day. | R-79 | ✗ R-99 15768ms |
| Then I do my homework, first I have a snack. | R-80 | ✓ 17158ms |
| How long take it to school? | R-81 | ✓ 16407ms |
| How you go to the library every day? | R-82 | ✓ 17364ms |
| She gets in the train every morning. | R-83 | ✓ 16899ms |
| The bank is on the zoo in our town. | R-84 | ✗ R-03 17778ms |
| Where the landmark is in this town? | R-85 | ✓ 15846ms |
| There are a lot bananas on this street. | R-86 | ✗ R-56 3448ms |
| He works a library as a teacher. | R-87 | ✓ 3348ms |
| What does he works? | R-88 | ✓ 3463ms |
| He would like be a designer someday. | R-89 | ✗ R-59 3463ms |
| The game makes him to embarrassed every time. | R-90 | ✓ 3874ms |
| He is so much excited after the race. | R-91 | ✓ 3641ms |
| Why she is excited today? | R-92 | ✓ 3354ms |
| It's eight dollar for this cap. | R-93 | ✓ 3434ms |
| I have this fork, please? | R-94 | ✓ 3867ms |
| He buyed a car his sister yesterday. | R-95 | ✓ 3821ms |
| She studies at her bedroom every evening. | R-96 | ✗ R-66 3338ms |
| Her house is four bedrooms and a big garage. | R-97 | ✗ R-77 3745ms |
| This bathroom is there, near the window. | R-98 | ✗ 놓침 (ok) 2727ms |
| He don't likes rainy days. | R-99 | ✓ 3943ms |
| Do they plays chess well? | R-100 | ✗ R-02 3478ms |
| Hi, Ben! | 정상 | ✗ 오교정 R-02 3220ms |
| Good morning, everyone! | 정상 | ✓ 정상 유지 2468ms |
| This is my dad. | 정상 | ✓ 정상 유지 2504ms |
| These are my cousins. | 정상 | ✓ 정상 유지 2504ms |
| I have a pencil. | 정상 | ✓ 정상 유지 2499ms |
| There is a cup on the table. | 정상 | ✓ 정상 유지 2686ms |
| Dogs can swim well. | 정상 | ✓ 정상 유지 2554ms |
| I have an apple. | 정상 | ✓ 정상 유지 2513ms |
| I want some water. | 정상 | ✓ 정상 유지 2512ms |
| I see a blue bird. | 정상 | ✓ 정상 유지 2573ms |
| **규칙 적중** | | **72/100** |
| **정상 문장 유지** | | 9/10 |
| **평균 응답** | | 9485ms |

판정: ✓ 정답 규칙 · ✗ R-xx 다른 규칙 · ✗ 놓침(ok) · ✓ 정상 유지 · ✗ 오교정 · ! 실패(호출 오류)
고친 문장 등 원본 응답은 같은 이름의 .json 참고.
