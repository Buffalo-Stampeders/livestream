#!/usr/bin/env python3
"""
Pull The Villages High School's upcoming Hudl Fan broadcasts via Hudl's public GraphQL API.
No login, cookies, or API key required. Prints one JSON object per broadcast.

Usage:  python3 hudl_upcoming.py [days_ahead]   (default 120)
        python3 hudl_upcoming.py --archived       (past Hudl broadcasts, i.e. replays / on demand)

The default mode only sees broadcasts that are still "Upcoming", so a game streamed on Hudl that
was never caught before it aired is never reported. --archived lists every archived broadcast
(Hudl's "Past Livestreams") so those can be added as compact "Watch On Demand" rows.
"""
import json, sys, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

GQL = "https://www.hudl.com/api/public/graphql/query"
SCHOOL_ID = "U2Nob29sNzkyNQ=="   # The Villages High School (org 7925) — base64 of "School7925"
WATCH_BASE = "https://fan.hudl.com/usa/fl/the-villages/organization/7925/the-villages-high-school/watch?b="

# Hudl sportId enum. 1, 2, 4 and 6 are confirmed against The Villages' own broadcasts
# (6 is Soccer, not Softball); the rest follow Hudl's enum order and are unverified here.
SPORT = {1: "Football", 2: "Basketball", 3: "Wrestling", 4: "Volleyball", 5: "Baseball", 6: "Soccer",
         7: "Lacrosse", 8: "Golf", 9: "Gymnastics", 10: "Softball", 11: "Swimming and Diving",
         12: "Track and Field", 13: "Ice Hockey", 14: "Field Hockey", 15: "Water Polo",
         16: "Cheerleading", 17: "Dance", 18: "Tennis", 19: "Cross Country"}
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

ARCHIVED_QUERY = """
query Web_Fan_GetBroadcasts_r1($input: GetBroadcastsPaginatedInput!) {
  broadcasts(input: $input) {
    edges { node { id status title requireLogin broadcastDateUtc mediumThumbnail
                   scheduleEntrySummary { timeUtc sportId genderId scheduleEntryLocation
                                          opponentDetails { name } } } }
    pageInfo { endCursor hasNextPage }
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

def archived():
    cursor = None
    while True:
        inp = {"first": 25, "sortByAscending": False, "sortType": "BROADCAST_DATE",
               "schoolIds": [SCHOOL_ID], "teamIds": [], "broadcastStatusFilter": "ARCHIVED"}
        if cursor:
            inp["after"] = cursor
        page = gql(ARCHIVED_QUERY, {"input": inp}, "Web_Fan_GetBroadcasts_r1")["broadcasts"]
        for edge in page["edges"]:
            b = edge["node"]
            e = b.get("scheduleEntrySummary") or {}
            if not e:
                continue
            print(json.dumps({
                "status":          b.get("status"),
                "title":           b.get("title"),
                # Scheduled game time; broadcastDateUtc is when the stream started and can be odd (e.g. 5:40:25).
                "kickoff_utc":     e.get("timeUtc") or b.get("broadcastDateUtc"),
                "sport":           SPORT.get(e["sportId"], f"sport:{e['sportId']}"),
                "gender":          GENDER.get(e["genderId"], f"gender:{e['genderId']}"),
                "opponent":        (e.get("opponentDetails") or {}).get("name"),
                "location":        LOCATION.get(e["scheduleEntryLocation"], "?"),
                "produced_by_opponent": e["scheduleEntryLocation"] != 1,
                "paid_access":     b.get("requireLogin") == "ppv",
                "watch_url":       WATCH_BASE + urllib.parse.quote(b["id"], safe=""),
                "thumbnail":       b.get("mediumThumbnail"),
                "hudl_broadcast_id": b["id"],
            }))
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--archived":
        archived()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
