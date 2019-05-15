# Rhasspy Timer Example

Example of using Rhasspy and NodeRED to set a timer for some number of hours, minutes, and seconds.

## Description

The grammar in `sentences.ini` allows for sentences that set a timer for 0-9 hours with 0-59 seconds and minutes.
Time expressions like "one and a half hours" are also supported.

Rhasspy's support for inline word replacements is used extensively to make intent handling easier.
Tokens like "one" and "two" are expressed as "one:1" and "two:2" in the grammar, meaning the spoken word "one" will be replaced with the token "1" during intent recognition. The only oddity with this approach is numbers made up of multiple words like "twenty two", which will show up as "20 2" in the recognized intent. The NodeRED flow handles this by simply summing the values in the hour/minute/second strings.

## Files

* `sentences.ini` - grammar for spoken sentences
* `flow.js` - NodeRED flow that interacts with Rhasspy
