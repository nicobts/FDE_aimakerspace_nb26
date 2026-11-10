# TC5 measurement

Model `ollama_chat/qwen3.5:9b`, 2026-11-10, one run per cell. All numbers *measured* by `measure.py`.

## Demo scale (passages cut to 200 characters)

**1 search** (q08: How long does a pasteurised cold brew coffee stay stable in the fridge, and does the roast level of the beans matter?)

| way | model calls | capability calls | seconds | tokens | bytes per response | tool calls per turn | gold cited | skipped the search |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pipeline | 1 | 1 | 35.1 | 681 | 1557 | [0] | 1/1 | 0 of 1 |
| tool loop | 2 | 2 | 61.9 | 2037 | 1595 | [2, 0] | 0/1 | 0 of 1 |
| subagent | 4 | 2 | 106.6 | 2808 | 1558 | [2, 0, 0, 0] | 0/1 | 0 of 1 |

**several searches** (q13: What have coffee by-products been turned into: can cascara work as an edible food coating, and what nutrients do spent coffee grounds and silverskin contain?)

| way | model calls | capability calls | seconds | tokens | bytes per response | tool calls per turn | gold cited | skipped the search |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pipeline | 1 | 1 | 45.1 | 720 | 1645 | [0] | 2/2 | 0 of 1 |
| tool loop | 2 | 3 | 77 | 2677 | 1684 | [3, 0] | 2/2 | 0 of 1 |
| subagent | 5 | 3 | 173.6 | 4223 | 1679 | [3, 0, 0, 0, 0] | 2/2 | 0 of 1 |

## Real scale (passages as shipped, up to 2,500 characters)

**1 search** (q08: How long does a pasteurised cold brew coffee stay stable in the fridge, and does the roast level of the beans matter?)

| way | model calls | capability calls | seconds | tokens | bytes per response | tool calls per turn | gold cited | skipped the search |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pipeline | 1 | 1 | 17.4 | 1917 | 6973 | [0] | 1/1 | 0 of 1 |
| tool loop | 2 | 2 | 70.7 | 4498 | 7296 | [2, 0] | 1/1 | 0 of 1 |
| subagent | 4 | 2 | 120.9 | 5496 | 7486 | [2, 0, 0, 0] | 1/1 | 0 of 1 |

**several searches** (q13: What have coffee by-products been turned into: can cascara work as an edible food coating, and what nutrients do spent coffee grounds and silverskin contain?)

| way | model calls | capability calls | seconds | tokens | bytes per response | tool calls per turn | gold cited | skipped the search |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pipeline | 1 | 1 | 18.2 | 2274 | 8960 | [0] | 2/2 | 0 of 1 |
| tool loop | 2 | 1 | 73.7 | 3182 | 8960 | [1, 0] | 2/2 | 1 of 2 |
| subagent | 5 | 3 | 154 | 9481 | 8995 | [3, 0, 0, 0, 0] | 2/2 | 0 of 1 |
