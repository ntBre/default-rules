#!/bin/sh
sqlite3 -markdown categories.db "SELECT code, name, category FROM rules ORDER BY code" > categories.md
