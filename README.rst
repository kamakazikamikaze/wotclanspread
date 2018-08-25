Clan Tank Viewer
================

*A simple example of what can be done if you stop running 5-man arty platoons*

What is this?
=============

Ever wanted to view who in your clan has what tank, or see all the tanks unlocked by a player, but in spreadsheet form?

No?

Too bad, I made this anyways.

Why?
====

Back in 2016 or so, while I was still active with the RDDT clan, I created this script to help the clan leaders
coordinate competitive matches. It became critical for them to be able to see who-owned-what-tier-tanks and check how
long players have been inactive for. Although hardly anyone else will really find this useful, I've decided to publish it.

How do I set this up for my own clan?
=====================================

This script requires a WarGaming API key, a Google Drive OAuth token, and machine to run it from (with Python 2 or 3).
Please be smart and never publish these credentials anywhere.

* `WarGaming Develper console <https://developers.wargaming.net/>`_
* `Google OAuth tokens <http://gspread.readthedocs.org/en/latest/oauth2.html>`_
* `Python <https://www.python.org/downloads/>`_

In our case, I have a dedicated Linux server that runs the script every hour via a Cron job. This will run just as well
from Windows or macOS.

What is the end result?
=======================

If you'd like a sample, I have a read-only link for the
`RDDT clan spreadsheet here <https://docs.google.com/spreadsheets/d/1mwAh83IryBxvr_IaTbKgzu-I8CU-Zuk8wlPniB6uf68/edit?usp=sharing>`_.
Feel free to tinker with the filters, they're specific to your session and will not modify the original doc.

F.A.Q.
======

"Could I get help with running the script?"
-------------------------------------------

If you are experiencing Python-specific issues with running the script, please open a ticket with your error message,
OS, Python version, and any additional comments.

"Could you run the script for me?"
----------------------------------

No.

"Do you accept feature requests?"
---------------------------------

Maybe. I haven't touched the code for this in a while and I don't plan on maintaining it as a public service. Open a
ticket and see.

"Could you export this to a different scripting language, like PHP or Javascript?"
----------------------------------------------------------------------------------

No.

"Could you modify this to work with OneDrive, Office365, or OpenPyXL?"
----------------------------------------------------------------------

*Inhales sharply*

No.
