#!/usr/bin/env python3
"""
Pull The Villages High School's upcoming Hudl Fan broadcasts via Hudl's public GraphQL API.
No login, cookies, or API key required. Prints one JSON object per broadcast.

Usage:  python3 hudl_upcoming.py [days_ahead]   (default 120)
"""
import json, sys, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

GQL = "https://www.hudl.com/api/public/graphql/query"
SCHOOL_ID = "U2Nob29sNzkyNQ=="   # The Villages High School (org 7925) — base64 of "School7925"
WATCH_BASE = "https://fan.hudl.com/usa/fl/the-villages/organization/7925/the-villages-high-school/watch?b="

SPORT = {1: "Football", 2: "Basketball", 3: "Soccer", 4: "Volleyball", 5: "Baseball", 6: "Softball",
         7: "Lacrosse", 8: "Wrestling", 9: "Swimming and Diving", 10: "Track and Field", 11: "Tennis",
         12: "Golf", 13: "Cross Country", 14: "Flag Football", 15: "Cheerleading"}
GENDER = {0: "Boys", 1: "Girls", 2: "Coed"}
LOCATION = {1: "Home", 2: "Away", 3: "Neutral"}

SCHEDULE_QUERY = """
query Web_Fan_GetScheduleEntrySummaries_r1($input: GetScheduleEntryPublicSummariesInput!) {
  scheduleEntryPublicSummaries(input: $input) {
    items { scheduleEntryId timeUtc isTimeTba sportId genderId scheduleEntryLocation broadcastStatus
            opponentDetails { name shortName profileImageUri } }
    totalCount
  }
}"""

BROADCAST_QUERY = """
query Web_Fan_GetBroadcastByScheduleEntryId_r1($scheduleEntryId: ID!) {
  getBroadcastByScheduleEntryId(scheduleEntryId: $scheduleEntryId) {
    id broadcastId status available requireLogin accessPassIds broadcastDateUtc timezone
    title siteTitle mediumThumbnail
  }
}"""

def gql(query, variables, op):
    body = json.dumps({"operationName": op, "variables": variables, "query": query}).encode()
    req = urllib.request.Request(GQL, data=body, headers={"content-type": "application/json",
                                                           "user-agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]

def main(days_ahead=120):
    now = datetime.now(timezone.utc)
    sched = gql(SCHEDULE_QUERY, {"input": {
        "sortType": "SCHEDULE_ENTRY_DATE", "schoolIds": [SCHOOL_ID], "sortByAscending": True,
        "filterStartDate": now.isoformat().replace("+00:00", "Z"),
        "filterEndDate": (now + timedelta(days=days_ahead)).isoformat().replace("+00:00", "Z")}},
        "Web_Fan_GetScheduleEntrySummaries_r1")["scheduleEntryPublicSummaries"]["items"]

    for e in sched:
        if not e.get("broadcastStatus"):          # no broadcast attached to this schedule entry
            continue
        b = gql(BROADCAST_QUERY, {"scheduleEntryId": e["scheduleEntryId"]},
                "Web_Fan_GetBroadcastByScheduleEntryId_r1")["getBroadcastByScheduleEntryId"]
        if not b or b.get("status") != "Upcoming":
            continue
        print(json.dumps({
            "kickoff_utc":     b.get("broadcastDateUtc") or e["timeUtc"],
            "sport":           SPORT.get(e["sportId"], f"sport:{e['sportId']}"),
            "gender":          GENDER.get(e["genderId"], f"gender:{e['genderId']}"),
            "opponent":        e["opponentDetails"]["name"],
            "location":        LOCATION.get(e["scheduleEntryLocation"], "?"),
            "produced_by_opponent": e["scheduleEntryLocation"] != 1,
            "paid_access":     b.get("requireLogin") == "ppv",
            "watch_url":       WATCH_BASE + urllib.parse.quote(b["id"], safe=""),
            "thumbnail":       b.get("mediumThumbnail"),
            "hudl_broadcast_id": b["id"],
        }))

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
