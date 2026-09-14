# /fix 비교 실험 — norag-gemini-qwen32b — 2026-09-14T11:17:25 · eval 110문장 · 규칙 100개 · 규칙 전부 (검색 없음) · 프롬프트 fix_fallback.txt

| 문장 | 정답 | local (qwen2.5:32b-instruct) |
|---|---|---|
| I hungry now. | R-01 | ✓ 7388ms |
| Good evening Dad. | R-02 | ✗ 놓침 (ok) 2420ms |
| This is Tom pencil. | R-03 | ✓ 3218ms |
| This is my daughters. | R-04 | ✗ R-03 3422ms |
| There are a book on the desk. | R-05 | ✓ 3299ms |
| She a grade has every day. | R-06 | ✓ 16446ms |
| The bird can runs fast. | R-07 | ✓ 3289ms |
| This birds are amazing. | R-08 | ✓ 3265ms |
| I have many soup. | R-09 | ✓ 3186ms |
| I want to a dessert. | R-10 | ✓ 3314ms |
| I see leaf a black. | R-11 | ✗ R-06 3224ms |
| I have nine pencil. | R-12 | ✗ R-38 3339ms |
| He was first in line. | R-13 | ✓ 3268ms |
| This is cold today. | R-14 | ✓ 3097ms |
| A storm will hits the coast. | R-15 | ✓ 3652ms |
| Trees bloom on spring. | R-16 | ✓ 3246ms |
| He wear a blue coat now. | R-17 | ✓ 3391ms |
| Ear is cold. | R-18 | ✗ R-14 3171ms |
| I like dance. | R-19 | ✓ 3113ms |
| I enjoy collect. | R-20 | ✓ 3120ms |
| I have a test in friday. | R-21 | ✓ 3496ms |
| I visit usually my grandparents every month. | R-22 | ✓ 3305ms |
| We go to school by a subway. | R-23 | ✓ 3670ms |
| We go to library every day. | R-24 | ✓ 3534ms |
| She wants to be designer. | R-25 | ✓ 3242ms |
| My uncle is dancer. | R-26 | ✓ 3528ms |
| She is bored for her son. | R-27 | ✓ 3560ms |
| He felt very too nervous to continue. | R-28 | ✓ 3573ms |
| How many is our money? | R-29 | ✓ 3238ms |
| The furniture is on the bedroom. | R-30 | ✓ 3104ms |
| He buy new shoes yesterday. | R-31 | ✓ 3312ms |
| A farmer harvest corn in fall. | R-32 | ✗ R-16 3274ms |
| I have two snack. | R-33 | ✗ R-38 3328ms |
| I have a elephant. | R-34 | ✗ R-44 3151ms |
| He is eat lunch now. | R-35 | ✗ R-31 3356ms |
| She are my cousin. | R-36 | ✓ 3216ms |
| It is cold yesterday. | R-37 | ✗ R-07 3147ms |
| I have pencil. | R-38 | ✓ 3297ms |
| How you are this evening? | R-39 | ✗ R-49 3266ms |
| Great to meet you, also. | R-40 | ✓ 3286ms |
| You welcome, Tom. | R-41 | ✓ 3296ms |
| He has a brother a cousin. | R-42 | ✓ 3445ms |
| Her grandparents is kind. | R-43 | ✓ 3620ms |
| My daughter is nine year old. | R-44 | ✓ 3360ms |
| You close the door, please. | R-45 | ✓ 17816ms |
| Who homework is this? | R-46 | ✓ 3230ms |
| My bag is at the desk and the window. | R-47 | ✓ 3562ms |
| A bear can not flies. | R-48 | ✗ R-07 3342ms |
| There isn't many creatures in this zoo. | R-49 | ✓ 3681ms |
| A bird is strong than a cat. | R-50 | ✓ 3501ms |
| He would like to a juice. | R-51 | ✓ 3048ms |
| I don't have some bananas at home. | R-52 | ✓ 3319ms |
| He drank a milk glass after dinner. | R-53 | ✗ R-23 3574ms |
| He likes purples balloons at the party. | R-54 | ✗ R-50 3450ms |
| What animal you like the best? | R-55 | ✗ ?R-046 3436ms |
| That clock looks brownly in this light. | R-56 | ✗ R-66 3627ms |
| How many plate is there in the room? | R-57 | ✗ R-09 3689ms |
| He has one triple the money now. | R-58 | ✓ 3469ms |
| There are hundred of bikes on the highway. | R-59 | ✓ 3661ms |
| How's the weather like today? | R-60 | ✓ 3487ms |
| It is getting warmly these days. | R-61 | ✓ 3597ms |
| He carries an umbrella because cold. | R-62 | ✓ 3510ms |
| She goes to skate every December. | R-63 | ✗ R-31 3364ms |
| Fall is coolest season of all. | R-64 | ✓ 3716ms |
| She travels while August every year. | R-65 | ✓ 3196ms |
| She wears off her gloves at home. | R-66 | ✓ 3575ms |
| Her pants is dirty. | R-67 | ✓ 3234ms |
| He looks coolly in his new dress. | R-68 | ✓ 3538ms |
| He has backache now. | R-69 | ✓ 3578ms |
| He washes hands before eating. | R-70 | ✓ 3664ms |
| He has white tooths. | R-71 | ✓ 3039ms |
| He plays a baseball after school. | R-72 | ✗ R-22 3426ms |
| Let's biking around the park. | R-73 | ✓ 3405ms |
| They are good at play soccer. | R-74 | ✓ 3564ms |
| He spends time to paint every day. | R-75 | ✓ 3510ms |
| How many often do you paint at home? | R-76 | ✓ 3511ms |
| He is interested at drawing these days. | R-77 | ✓ 3406ms |
| What time it is now? | R-78 | ✗ R-88 3461ms |
| He wakes up on one o'clock every day. | R-79 | ✗ R-99 11142ms |
| Then I do my homework, first I have a snack. | R-80 | ✓ 8882ms |
| How long take it to school? | R-81 | ✓ 3706ms |
| How you go to the library every day? | R-82 | ✓ 3508ms |
| She gets in the train every morning. | R-83 | ✓ 3339ms |
| The bank is on the zoo in our town. | R-84 | ✗ R-30 3559ms |
| Where the landmark is in this town? | R-85 | ✓ 3457ms |
| There are a lot bananas on this street. | R-86 | ✗ R-56 3452ms |
| He works a library as a teacher. | R-87 | ✓ 3352ms |
| What does he works? | R-88 | ✓ 3270ms |
| He would like be a designer someday. | R-89 | ✗ R-59 3517ms |
| The game makes him to embarrassed every time. | R-90 | ✓ 3760ms |
| He is so much excited after the race. | R-91 | ✓ 7855ms |
| Why she is excited today? | R-92 | ✓ 7530ms |
| It's eight dollar for this cap. | R-93 | ✓ 3448ms |
| I have this fork, please? | R-94 | ✓ 3884ms |
| He buyed a car his sister yesterday. | R-95 | ✓ 3312ms |
| She studies at her bedroom every evening. | R-96 | ✗ R-66 3280ms |
| Her house is four bedrooms and a big garage. | R-97 | ✗ R-77 3700ms |
| This bathroom is there, near the window. | R-98 | ✗ 놓침 (ok) 2707ms |
| He don't likes rainy days. | R-99 | ✓ 3784ms |
| Do they plays chess well? | R-100 | ✗ R-02 3727ms |
| Hi, Ben! | 정상 | ✗ 오교정 R-02 3234ms |
| Good morning, everyone! | 정상 | ✓ 정상 유지 2469ms |
| This is my dad. | 정상 | ✓ 정상 유지 2504ms |
| These are my cousins. | 정상 | ✓ 정상 유지 2501ms |
| I have a pencil. | 정상 | ✓ 정상 유지 2482ms |
| There is a cup on the table. | 정상 | ✓ 정상 유지 2679ms |
| Dogs can swim well. | 정상 | ✓ 정상 유지 2569ms |
| I have an apple. | 정상 | ✓ 정상 유지 2504ms |
| I want some water. | 정상 | ✓ 정상 유지 2529ms |
| I see a blue bird. | 정상 | ✓ 정상 유지 2560ms |
| **규칙 적중** | | **72/100** |
| **정상 문장 유지** | | 9/10 |
| **평균 응답** | | 3807ms |

판정: ✓ 정답 규칙 · ✗ R-xx 다른 규칙 · ✗ 놓침(ok) · ✓ 정상 유지 · ✗ 오교정 · ! 실패(호출 오류)
고친 문장 등 원본 응답은 같은 이름의 .json 참고.
