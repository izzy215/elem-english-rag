# /fix 비교 실험 — ollama32b-rag-top8 — 2026-09-15T15:45:12 · eval 360문장 · 규칙 100개 · RAG 파이프라인 (검색 상위 8 + 공통 규칙, 임베딩 intfloat/multilingual-e5-base) · 프롬프트 fix_fallback.txt

| 문장 | 정답 | local (qwen2.5:32b-instruct) |
|---|---|---|
| I hungry now. | R-01 | ✗ R-36 10001ms |
| The garden pale. | R-01 | ✓ 4449ms |
| This soup salty. | R-01 | ✓ 4466ms |
| Good evening Dad. | R-02 | ✓ 5260ms |
| Good night Amy. | R-02 | ✓ 5073ms |
| Thanks Tom. | R-02 | ✓ 5069ms |
| This is Tom pencil. | R-03 | ✗ 놓침 (ok) 4665ms |
| She is niece. | R-03 | ✗ R-26 4742ms |
| The boy with the ball is brother. | R-03 | ✗ R-42 3306ms |
| This are my daughter. | R-04 | ✗ 놓침 (ok) 4952ms |
| These is my relatives. | R-04 | ✓ 4465ms |
| These are my son. | R-04 | ✓ 4711ms |
| Look! There are a cat under the chair. | R-05 | ✓ 4813ms |
| There are a chair in the room. | R-05 | ✓ 4559ms |
| There are a teacher in the classroom. | R-05 | ✓ 4512ms |
| She a grade has every day. | R-06 | ✓ 5104ms |
| She a schedule learns every day. | R-06 | ✓ 5269ms |
| He his lunch eats every day. | R-06 | ✗ R-32 4806ms |
| The bird can runs fast. | R-07 | ✓ 4807ms |
| The cat can jumps high. | R-07 | ✓ 4587ms |
| The eagle can flies high. | R-07 | ✓ 4889ms |
| Wow, this monkeys are so funny! | R-08 | ✓ 4977ms |
| This fishes are amazing. | R-08 | ✓ 4310ms |
| This rabbits are amazing. | R-08 | ✓ 4383ms |
| I have many soup. | R-09 | ✓ 4403ms |
| I need many sugar. | R-09 | ✓ 4518ms |
| Please give me many rice for dinner. | R-09 | ✓ 4639ms |
| I want to a dessert. | R-10 | ✓ 2983ms |
| I want to a meal. | R-10 | ✓ 2975ms |
| I want to a snack. | R-10 | ✓ 3119ms |
| I see leaf a black. | R-11 | ✓ 4740ms |
| I see shoe a yellow. | R-11 | ✓ 4828ms |
| I see window a red. | R-11 | ✓ 4708ms |
| I have nine pencil. | R-12 | ✓ 4618ms |
| I have one bananas. | R-12 | ✓ 4639ms |
| I have two cookie. | R-12 | ✗ R-33 4613ms |
| He was first in line. | R-13 | ✓ 4607ms |
| He was second in the race. | R-13 | ✓ 4658ms |
| She was first at school today. | R-13 | ✓ 4791ms |
| This is cold today. | R-14 | ✗ 놓침 (ok) 4479ms |
| This is snowy today. | R-14 | ✓ 4380ms |
| This is windy today. | R-14 | ✓ 4330ms |
| A storm will hits the coast. | R-15 | ✓ 4674ms |
| I think it will snows a lot this weekend. | R-15 | ✗ R-32 5256ms |
| My mom says it will rains. | R-15 | ✓ 5200ms |
| Trees bloom on spring. | R-16 | ✓ 5039ms |
| We enjoy outdoor activities on fall. | R-16 | ✓ 4692ms |
| The leaves turn red on fall. | R-16 | ✓ 4270ms |
| He wear a blue coat now. | R-17 | ✓ 5026ms |
| She wear a pretty skirt now. | R-17 | ✓ 4670ms |
| She wear a red hat now. | R-17 | ✓ 4704ms |
| Ear is cold. | R-18 | ✓ 4625ms |
| Eye is cold. | R-18 | ✓ 4941ms |
| Hand hurts. | R-18 | ✓ 4619ms |
| I like dance. | R-19 | ✗ 놓침 (ok) 4539ms |
| I like sing. | R-19 | ✓ 4662ms |
| I like ride a bike. | R-19 | ✓ 4696ms |
| I enjoy collect. | R-20 | ✓ 4659ms |
| I enjoy paint. | R-20 | ✓ 4393ms |
| I enjoy play. | R-20 | ✓ 4412ms |
| I have a test in friday. | R-21 | ✓ 5054ms |
| We have a quiz in tuesday. | R-21 | ✓ 5171ms |
| I have a test in sunday. | R-21 | ✓ 5093ms |
| I visit usually my grandparents every month. | R-22 | ✓ 4595ms |
| I visit usually my grandparents on Saturday. | R-22 | ✓ 5085ms |
| He goes always to school early. | R-22 | ✓ 4644ms |
| We go to school by a subway. | R-23 | ✓ 4841ms |
| We go to school by a taxi. | R-23 | ✓ 5248ms |
| They travel by a boat. | R-23 | ✓ 4847ms |
| We go to library every day. | R-24 | ✓ 4945ms |
| We go to museum every day. | R-24 | ✓ 5072ms |
| We go to hospital every day. | R-24 | ✗ R-87 4765ms |
| She wants to be designer. | R-25 | ✓ 4895ms |
| She wants to be scientist. | R-25 | ✓ 4557ms |
| She wants to be writer. | R-25 | ✓ 4787ms |
| My uncle is dancer. | R-26 | ✓ 4810ms |
| My uncle is pilot. | R-26 | ✓ 4782ms |
| My uncle is singer. | R-26 | ✓ 4686ms |
| She is bored for her son. | R-27 | ✓ 3720ms |
| She is worried of the test. | R-27 | ✓ 5008ms |
| She is surprised for his friend. | R-27 | ✗ 놓침 (ok) 5137ms |
| He felt very too nervous to continue. | R-28 | ✓ 4857ms |
| He was very too jealous to speak. | R-28 | ✓ 4954ms |
| He was very too proud to speak. | R-28 | ✗ R-27 5555ms |
| How many is our money? | R-29 | ✓ 4555ms |
| How many is this bag? | R-29 | ✓ 4541ms |
| How many is this toy? | R-29 | ✓ 4526ms |
| The furniture is on the bedroom. | R-30 | ✓ 4934ms |
| The garage is on the neighborhood. | R-30 | ✓ 4587ms |
| The fish is on the water. | R-30 | ✓ 4388ms |
| He buy new shoes yesterday. | R-31 | ✓ 4442ms |
| I say thanks to my new friend yesterday. | R-31 | ✓ 4609ms |
| She eat a big cheese last night. | R-31 | ✓ 4702ms |
| A farmer harvest corn in fall. | R-32 | ✓ 5308ms |
| She dye her shirt blue. | R-32 | ✓ 5119ms |
| She invite her friends every weekend. | R-32 | ✗ R-33 5184ms |
| I have two snack. | R-33 | ✗ R-12 4602ms |
| She has three coat. | R-33 | ✗ R-12 4659ms |
| We saw five motorcycle on the road. | R-33 | ✓ 4659ms |
| I have a elephant. | R-34 | ✓ 4619ms |
| I have a umbrella. | R-34 | ✓ 4638ms |
| I have a orange. | R-34 | ✓ 4279ms |
| He is eat lunch now. | R-35 | ✓ 4354ms |
| She is read a book now. | R-35 | ✓ 4616ms |
| They are watch TV now. | R-35 | ✓ 4607ms |
| She are my cousin. | R-36 | ✓ 4473ms |
| You is my best friend. | R-36 | ✓ 4378ms |
| They is my classmates. | R-36 | ✓ 4149ms |
| It is cold yesterday. | R-37 | ✓ 4287ms |
| They are at school yesterday. | R-37 | ✓ 4338ms |
| I am tired last night. | R-37 | ✓ 4449ms |
| I have pencil. | R-38 | ✓ 4411ms |
| She wants cookie. | R-38 | ✗ R-10 4624ms |
| He carries umbrella. | R-38 | ✓ 4764ms |
| How you are this evening? | R-39 | ✓ 4742ms |
| How you are on your birthday? | R-39 | ✓ 4637ms |
| How you are, Tom? | R-39 | ✓ 4830ms |
| Great to meet you, also. | R-40 | ✓ 4899ms |
| So happy to meet you, also. | R-40 | ✓ 4659ms |
| Wonderful to meet you, also. | R-40 | ✓ 4718ms |
| You welcome, Tom. | R-41 | ✓ 4817ms |
| You welcome, Amy. | R-41 | ✓ 4639ms |
| You welcome, my friend. | R-41 | ✓ 4705ms |
| He has a brother a cousin. | R-42 | ✓ 4729ms |
| She has a sister a brother. | R-42 | ✓ 4711ms |
| I have a mom a dad. | R-42 | ✗ 놓침 (ok) 3236ms |
| Her grandparents is kind. | R-43 | ✓ 4962ms |
| Our grandparents is wise. | R-43 | ✓ 4534ms |
| Their grandparents is generous. | R-43 | ✓ 4590ms |
| My daughter is nine year old. | R-44 | ✓ 3395ms |
| My grandchild is nine year old. | R-44 | ✓ 3457ms |
| My relative is nine year old. | R-44 | ✓ 3223ms |
| You close the door, please. | R-45 | ✓ 4847ms |
| You open the box, please. | R-45 | ✓ 4576ms |
| You clean the desk, please. | R-45 | ✗ OTHER 3067ms |
| Who homework is this? | R-46 | ✗ 놓침 (ok) 4596ms |
| Who subject is this? | R-46 | ✗ 놓침 (ok) 4597ms |
| Who test is this? | R-46 | ✗ 놓침 (ok) 4550ms |
| My bag is at the desk and the window. | R-47 | ✓ 4779ms |
| My book is at the desk and the bed. | R-47 | ✗ R-30 4586ms |
| My chair is at the desk and the wall. | R-47 | ✓ 4583ms |
| A bear can not flies. | R-48 | ✓ 4559ms |
| An insect can not flies. | R-48 | ✓ 3691ms |
| A turtle can not flies. | R-48 | ✓ 4710ms |
| There isn't many creatures in this zoo. | R-49 | ✓ 4754ms |
| There isn't many mammals in this zoo. | R-49 | ✓ 4510ms |
| There isn't many reptiles in this zoo. | R-49 | ✓ 4585ms |
| A bird is strong than a cat. | R-50 | ✓ 4818ms |
| A dog is strong than a rabbit. | R-50 | ✓ 4930ms |
| A lion is strong than a fox. | R-50 | ✓ 4955ms |
| He would like to a juice. | R-51 | ✓ 3288ms |
| She would like to a sandwich. | R-51 | ✗ R-10 3194ms |
| I would like to a milk. | R-51 | ✗ OTHER 3246ms |
| I don't have some bananas at home. | R-52 | ✓ 4779ms |
| I don't have some eggs at home. | R-52 | ✓ 4415ms |
| I don't have some pizza at home. | R-52 | ✓ 4788ms |
| He drank a milk glass after dinner. | R-53 | ✓ 5045ms |
| She ate a cake piece for dessert. | R-53 | ✓ 4954ms |
| He ate a pizza piece for lunch. | R-53 | ✗ 놓침 (ok) 3894ms |
| He likes purples balloons at the party. | R-54 | ✓ 4807ms |
| He likes purples kites in the sky. | R-54 | ✓ 4871ms |
| She likes oranges balloons at the party. | R-54 | ✓ 4807ms |
| What animal you like the best? | R-55 | ✓ 4611ms |
| What color you like the most? | R-55 | ✓ 4644ms |
| What subject you like the best? | R-55 | ✓ 4600ms |
| That clock looks brownly in this light. | R-56 | ✓ 3470ms |
| That lamp looks brownly in this light. | R-56 | ✓ 3571ms |
| That spoon looks brownly in this light. | R-56 | ✓ 4927ms |
| How many plate is there in the room? | R-57 | ✓ 4748ms |
| How many spoon is there on the shelf? | R-57 | ✓ 4867ms |
| How many cup is there on the table? | R-57 | ✓ 5004ms |
| He has one triple the money now. | R-58 | ✓ 4779ms |
| I have three double the candy now. | R-58 | ✓ 4712ms |
| She has four triple the money now. | R-58 | ✓ 4745ms |
| There are hundred of bikes on the highway. | R-59 | ✓ 4943ms |
| There are hundred of books in the library. | R-59 | ✓ 5139ms |
| There are thousand of stars in the sky. | R-59 | ✓ 4848ms |
| Mom, how's the weather like at the beach? | R-60 | ✓ 5107ms |
| How's the lightning like tomorrow? | R-60 | ! 실패 8526ms |
| How's the thunder like tomorrow? | R-60 | ✓ 4571ms |
| It is getting warmly these days. | R-61 | ✓ 5302ms |
| It is getting darkly outside. | R-61 | ✓ 4867ms |
| It is getting coldly this winter. | R-61 | ✓ 4895ms |
| He carries an umbrella because cold. | R-62 | ✓ 4994ms |
| He carries an umbrella because snowy. | R-62 | ✓ 4935ms |
| He carries an umbrella because windy. | R-62 | ✓ 4926ms |
| She goes to skate every December. | R-63 | ✓ 4885ms |
| He goes to swim every summer. | R-63 | ✓ 4762ms |
| They go to fish in spring. | R-63 | ✓ 5163ms |
| Today was coldest day of this year. | R-64 | ✓ 4771ms |
| My cat is fattest cat in town. | R-64 | ✗ R-50 4761ms |
| August is hottest month here. | R-64 | ✓ 5081ms |
| She travels while August every year. | R-65 | ✓ 4685ms |
| He reads while breakfast every morning. | R-65 | ! 실패 8456ms |
| They ski while vacation every winter. | R-65 | ✓ 4790ms |
| She wears off her gloves at home. | R-66 | ✓ 4870ms |
| He wears off his shoes at home. | R-66 | ✓ 4882ms |
| He wears off his socks at night. | R-66 | ✓ 4859ms |
| Her pants is dirty. | R-67 | ✓ 4740ms |
| My shoes is wet. | R-67 | ✓ 4520ms |
| His socks is warm. | R-67 | ✓ 4692ms |
| He looks coolly in his new dress. | R-68 | ✓ 4703ms |
| He looks coolly in his new hat. | R-68 | ✓ 4679ms |
| He looks coolly in his new skirt. | R-68 | ✓ 4850ms |
| He has backache now. | R-69 | ✓ 4792ms |
| She has earache tonight. | R-69 | ✓ 5093ms |
| They have stomachache after lunch. | R-69 | ✓ 4991ms |
| He washes hands before eating. | R-70 | ✗ 놓침 (ok) 3935ms |
| She brushes teeth every night. | R-70 | ✓ 5056ms |
| They wash face in the morning. | R-70 | ✓ 5149ms |
| He has white tooths. | R-71 | ✓ 4464ms |
| His foots are cold. | R-71 | ✗ OTHER 3531ms |
| She has small foots. | R-71 | ✓ 4560ms |
| My friends play a badminton at the park. | R-72 | ✓ 5034ms |
| Do you play a basketball on weekends? | R-72 | ✗ 놓침 (ok) 3329ms |
| She plays a badminton after school. | R-72 | ✓ 5069ms |
| Let's biking around the park. | R-73 | ✓ 4958ms |
| Let's dancing at the party. | R-73 | ✓ 4870ms |
| Let's playing badminton today. | R-73 | ✓ 5041ms |
| They are good at play soccer. | R-74 | ✗ R-73 3408ms |
| She is good at play tennis. | R-74 | ✗ R-72 3293ms |
| He is good at play baseball. | R-74 | ✓ 4947ms |
| He spends time to paint every day. | R-75 | ✓ 5216ms |
| I spend time to read every weekend. | R-75 | ✓ 5115ms |
| She spends time to dance every day. | R-75 | ✓ 5040ms |
| How many often do you paint at home? | R-76 | ✓ 3249ms |
| How many often do you study at home? | R-76 | ✓ 3252ms |
| How many often do you swim? | R-76 | ✗ OTHER 3121ms |
| My little sister is interested at space. | R-77 | ✓ 4803ms |
| She is interested at dancing these days. | R-77 | ✓ 4624ms |
| They are interested at soccer these days. | R-77 | ✓ 4590ms |
| Sorry, what time it is in Korea? | R-78 | ✓ 4733ms |
| Tom, what time it is? | R-78 | ✓ 4773ms |
| What time it is today? | R-78 | ✓ 4713ms |
| He wakes up on one o'clock every day. | R-79 | ✓ 4899ms |
| She wakes up on four o'clock every day. | R-79 | ✓ 4455ms |
| She wakes up on three o'clock every day. | R-79 | ✓ 4631ms |
| Then I do my homework, first I have a snack. | R-80 | ✗ OTHER 4274ms |
| Then I get dressed, first I wake up. | R-80 | ✗ OTHER 4146ms |
| Then I read a book, first I turn on the lamp. | R-80 | ✗ OTHER 4310ms |
| How long take it to school? | R-81 | ✓ 5235ms |
| How long take it to the library? | R-81 | ✓ 5067ms |
| How long take it to get to the airport? | R-81 | ✓ 5110ms |
| How your mom go to work? | R-82 | ✓ 4966ms |
| How you get to the zoo? | R-82 | ✓ 5062ms |
| How you go to church on Sunday? | R-82 | ✓ 4951ms |
| Hurry, get in the bus before it leaves! | R-83 | ✓ 4916ms |
| He gets in the subway every morning. | R-83 | ✓ 4738ms |
| They get in the airplane at the airport. | R-83 | ✓ 4794ms |
| The bank is on the zoo in our town. | R-84 | ✓ 4877ms |
| The hospital is on the school in our town. | R-84 | ✓ 5072ms |
| The theater is on the park in our town. | R-84 | ✓ 5267ms |
| Where the landmark is in this town? | R-85 | ✓ 5103ms |
| Where the suburb is in this town? | R-85 | ✓ 4938ms |
| Where the bakery is in this town? | R-85 | ✓ 4967ms |
| There are a lot bananas on this street. | R-86 | ✓ 5050ms |
| There are a lot cookies on this street. | R-86 | ✓ 4992ms |
| There are a lot oranges on this street. | R-86 | ✓ 5086ms |
| He works a library as a teacher. | R-87 | ✓ 5015ms |
| She works a hospital as a nurse. | R-87 | ✓ 4950ms |
| He works a bank in our town. | R-87 | ✓ 4811ms |
| Tell me, what does the new neighbor works? | R-88 | ✓ 4778ms |
| What does she works every day? | R-88 | ✓ 4711ms |
| What does your uncle works? | R-88 | ✓ 4978ms |
| He would like be a designer someday. | R-89 | ✓ 5040ms |
| He would like be a photographer someday. | R-89 | ✓ 5002ms |
| He would like be a writer someday. | R-89 | ✓ 5193ms |
| The game makes him to embarrassed every time. | R-90 | ✓ 4978ms |
| The game makes him to frustrated every time. | R-90 | ✓ 4980ms |
| The game makes him to grateful every time. | R-90 | ✓ 3329ms |
| He is so much excited after the race. | R-91 | ✓ 5078ms |
| He is so much hungry after the race. | R-91 | ✓ 5041ms |
| He is so much scared after the race. | R-91 | ✓ 5007ms |
| Why she is excited today? | R-92 | ✓ 4776ms |
| Why he is hungry now? | R-92 | ✓ 4648ms |
| Why they are scared? | R-92 | ✗ R-100 4506ms |
| It's eight dollar for this cap. | R-93 | ✓ 4796ms |
| It's nine dollar for this cap. | R-93 | ✓ 4319ms |
| It's ten dollar for this cap. | R-93 | ✓ 4812ms |
| I have this fork, please? | R-94 | ✓ 4970ms |
| I have this juice, please? | R-94 | ✗ OTHER 3545ms |
| I have this cookie, please? | R-94 | ✓ 5190ms |
| He buyed a car his sister yesterday. | R-95 | ! 실패 8690ms |
| He buyed a flower his sister yesterday. | R-95 | ! 실패 8725ms |
| He buyed a tree his sister yesterday. | R-95 | ! 실패 8880ms |
| She studies at her bedroom every evening. | R-96 | ✓ 4673ms |
| He reads at his room every night. | R-96 | ✓ 4503ms |
| They eat at the kitchen every morning. | R-96 | ✓ 4448ms |
| Her house is four bedrooms and a big garage. | R-97 | ✓ 4628ms |
| His house is two bathrooms and a kitchen. | R-97 | ✓ 4492ms |
| Their house is five rooms and a yard. | R-97 | ✓ 4513ms |
| This bathroom is there, near the window. | R-98 | ✗ 놓침 (ok) 5031ms |
| This kitchen is there, near the window. | R-98 | ✗ 놓침 (ok) 4946ms |
| This lamp is there, near the window. | R-98 | ✗ 놓침 (ok) 5108ms |
| He don't likes rainy days. | R-99 | ✗ 놓침 (ok) 4737ms |
| She don't likes cats. | R-99 | ✗ 놓침 (ok) 4626ms |
| We don't likes carrots. | R-99 | ✓ 4769ms |
| Do they plays chess well? | R-100 | ✓ 4774ms |
| Does he plays badminton well? | R-100 | ✓ 4989ms |
| Does she plays tennis well? | R-100 | ✓ 5007ms |
| Hi, Ben! | 정상 | ✓ 정상 유지 2318ms |
| Good morning, everyone! | 정상 | ✓ 정상 유지 2370ms |
| This is my dad. | 정상 | ✓ 정상 유지 3880ms |
| These are my two best friends. | 정상 | ✓ 정상 유지 3930ms |
| I have a new eraser in my bag. | 정상 | ✓ 정상 유지 4112ms |
| There is a cup on the table. | 정상 | ✓ 정상 유지 4018ms |
| Dogs can swim well. | 정상 | ✓ 정상 유지 3938ms |
| I have an apple. | 정상 | ✓ 정상 유지 2364ms |
| I want some juice with my lunch. | 정상 | ✓ 정상 유지 4155ms |
| I see a blue bird. | 정상 | ✓ 정상 유지 2425ms |
| I have three books. | 정상 | ✓ 정상 유지 3848ms |
| It is really windy at the beach. | 정상 | ✓ 정상 유지 4068ms |
| It will snow tomorrow. | 정상 | ✓ 정상 유지 3879ms |
| He is wearing a warm coat. | 정상 | ✓ 정상 유지 3982ms |
| My arm hurts. | 정상 | ✗ 오교정 R-18 3376ms |
| I like drawing. | 정상 | ✓ 정상 유지 2333ms |
| She enjoys singing. | 정상 | ✓ 정상 유지 2333ms |
| We have a quiz on Friday. | 정상 | ✓ 정상 유지 4038ms |
| She usually walks to school. | 정상 | ✓ 정상 유지 3917ms |
| My cousin goes to school by subway. | 정상 | ✓ 정상 유지 3999ms |
| They go to the park every day. | 정상 | ✓ 정상 유지 2543ms |
| My mom is a nurse. | 정상 | ✓ 정상 유지 2435ms |
| I am proud of my sister. | 정상 | ✓ 정상 유지 2461ms |
| This soup is too hot. | 정상 | ✓ 정상 유지 3139ms |
| How much is this bag? | 정상 | ✓ 정상 유지 2393ms |
| The ball is under the chair. | 정상 | ✓ 정상 유지 4034ms |
| I watched a movie yesterday. | 정상 | ✓ 정상 유지 4067ms |
| She reads books every night. | 정상 | ✓ 정상 유지 3933ms |
| I brush my teeth every day. | 정상 | ✓ 정상 유지 2674ms |
| My feet are cold. | 정상 | ✓ 정상 유지 2365ms |
| We play tag after lunch. | 정상 | ✓ 정상 유지 3962ms |
| Let's go swimming. | 정상 | ✓ 정상 유지 3632ms |
| He is good at cooking. | 정상 | ✓ 정상 유지 4164ms |
| What time is the movie tonight? | 정상 | ✓ 정상 유지 3848ms |
| I get up at seven. | 정상 | ✓ 정상 유지 4050ms |
| The library is next to the bank. | 정상 | ✓ 정상 유지 4033ms |
| There are a lot of flowers in the garden. | 정상 | ✓ 정상 유지 4141ms |
| My dad works at a bank. | 정상 | ✓ 정상 유지 2480ms |
| This game makes me happy. | 정상 | ✓ 정상 유지 4099ms |
| Our house has four rooms. | 정상 | ✓ 정상 유지 2413ms |
| I am sleepy after lunch. | 정상 | ✓ 정상 유지 2457ms |
| She is very kind. | 정상 | ✓ 정상 유지 3890ms |
| Hello, Amy! | 정상 | ✓ 정상 유지 2450ms |
| There are many students in my class. | 정상 | ✓ 정상 유지 2513ms |
| My parrot can say my name. | 정상 | ✓ 정상 유지 3928ms |
| I don't have much time. | 정상 | ✓ 정상 유지 3951ms |
| I want a hamburger. | 정상 | ✓ 정상 유지 3877ms |
| I see a red rose. | 정상 | ✓ 정상 유지 3923ms |
| I have two dogs. | 정상 | ✓ 정상 유지 3973ms |
| It is foggy this morning. | 정상 | ✓ 정상 유지 3283ms |
| She is wearing glasses. | 정상 | ✓ 정상 유지 4127ms |
| My tooth hurts when I eat ice cream. | 정상 | ✗ 오교정 R-71 5060ms |
| I like playing badminton. | 정상 | ✓ 정상 유지 4021ms |
| I enjoy reading comics. | 정상 | ✓ 정상 유지 2370ms |
| I have piano lessons on Wednesday. | 정상 | ✓ 정상 유지 3965ms |
| My family travels by car every summer. | 정상 | ✓ 정상 유지 4063ms |
| She wants to be a singer. | 정상 | ✓ 정상 유지 4008ms |
| My uncle is an actor. | 정상 | ✓ 정상 유지 3973ms |
| He is scared of dogs. | 정상 | ✓ 정상 유지 3823ms |
| Does your brother like spicy food? | 정상 | ✓ 정상 유지 3971ms |
| **규칙 적중** | | **252/300** |
| **정상 문장 유지** | | 58/60 |
| **평균 응답** | | 4471ms |

판정: ✓ 정답 규칙 · ✗ R-xx 다른 규칙 · ✗ 놓침(ok) · ✓ 정상 유지 · ✗ 오교정 · ! 실패(호출 오류)
고친 문장 등 원본 응답은 같은 이름의 .json 참고.
