import argparse
from babel.dates import format_date, format_datetime, format_time
import datetime
import dateparser
import json
import math
import os
import re
import requests
import string
from bs4 import BeautifulSoup
from requests_html import HTMLSession


# TODO: replace the tuples in this code with dictionaries using these keys.
KEY_TITLE = "title"
KEY_NAME = "name"
KEY_DATE = "date"
KEY_DATE_STRING = "date_string"
KEY_PLACE = "place"
KEY_URL = "url"
KEY_LANGUAGE = "language"
KEY_CITY = "city"
KEY_LINGUISTIC_REGION = "lregion"


# Returns a Date object (at midnight) for the given strptime format, or None on failure.
# If the year is not parsed (1900), it's set to the current year.
# https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
def maybeParseDate(date_string, format):
    try:
        dt = datetime.datetime.strptime(date_string, format)
        date = dt.date()
        if date.year == 1900:
            return datetime.date(datetime.datetime.today().year, date.month, date.day)
        return date
    except ValueError:
        return None


# All the scrape_ functions below extract events from various ticketing sytem pages.
# soup: BeautifulSoup object, see https://www.crummy.com/software/BeautifulSoup/bs4/doc/
# Return: array of tuples (title, event name, date, place, url, language)


# BilletWeb
def scrape_BilletWeb(soup, title, language):
    events = []
    for tag in soup.find_all("div", class_="multi_event_container"):
        child = tag.find("div", class_="multi_event_info_empty")
        if child:
            continue  # this container is empty

        child = tag.find("span", class_="multi_event_name_span")
        if not child:
            if not "multi_event_info_empty" in tag["class"]:
                print("BilletWeb name not found? ", tag)
            continue
        name = child.string

        child = tag.find("div", class_="multi_event_date")
        if child is None:
            print("Date not found?", tag)
            continue
        child2 = child.span
        if child2 is None:
            print("unexpected date:", child)
        date_strings = []  # deal with multi-dates
        for child3 in child2.find_all("span", class_="multi_event_time"):
            date_strings.append(child3.string)
        if len(date_strings) == 0:
            date_strings.append(child2.string)
        dates = []
        for date_string in date_strings:
            # TODO: there has got to be better ways to parse these strings.
            date = dateparser.parse(
                date_string,
                settings=dict(
                    {
                        "DATE_ORDER": "DMY",
                        "REQUIRE_PARTS": ["day", "month"],
                        "SKIP_TOKENS": [
                            "Mon",
                            "Tue",
                            "Wed",
                            "Thu",
                            "Fri",
                            "Sat",
                            "Sun",
                        ],
                    }
                ),
            )
            if not date:
                date = maybeParseDate(date_string, "%a %m/%d")  # ex: Sun 03/25
            if not date:
                date = maybeParseDate(
                    date_string[0:16], "%a %b %d, %Y"
                )  # ex: Sun Mar 03, 2023
            if not date:
                print(
                    "Cannot parse date, discarding event:",
                    date_string,
                    "(" + title + ")",
                )
                continue
            dates.append(date)

        child = tag.find("div", class_="multi_event_place")
        if not child:
            print("Place not found?", tag)
            continue
        place = child.span.string
        if not place:
            continue  # skip online-only events

        child = tag.find("div", class_="multi_event_button")
        if not child:
            print("No button found?", tag)
            continue
        child2 = child.find("a")
        if not child2:
            print("No URL found on button?", tag)
            continue
        url = child2["href"]
        if not url:
            print("Unable to extract URL?", tag)
            continue

        real_language = language
        if "Biodiversity Collage" in name:
            real_language = "en"
        for date in dates:
            events.append((title, name, date, place, url, real_language))
    return events


# BilletWeb
def scrape_BilletWebOLD(soup, title, language):
    events = []
    print("SCRAPING BILLETWEB: " + title)

    for tag in soup.find_all("div", class_="multi_event_info"):
        print("multi_event_info")
        child = tag.find("div", class_="multi_event_place")
        if not child:
            continue  # skip online-only events
        child2 = child.find("span", class_="title searchable")
        if not child2:
            continue  # skip online-only events
        print("présentiel")

        child = tag.find("span", class_="multi_event_name_span")
        if not child:
            continue
        name = child.string

        child = tag.find("div", class_="multi_event_date")
        if not child:
            continue
        date = child.string

        child = tag.parent.find("div", class_="multi_event_button")
        if not child:
            print("BUTTON NOT FOUND, skipping for event ", child2.string)
            continue
        child3 = child.find("a", class_="custom_color_block")
        if not child3:
            print("BLOCK NOT FOUND, skipping for event ", child2.string)
            continue
        if child3.has_attr("onclick"):
            m = re.match(r".*window.open.'(http.+?)'", child3["onclick"])
            if not m:
                print("URL NOT FOUND, skipping for event ", child2.string)
                continue
            url = m.group(1)
        else:
            url = child3["href"]

        events.append((name, date, child2.string, url, language))
        print("NAME: " + name)
        print("DATE: " + date)
        print("PLACE: " + child2.string)
    return events


# FresquesZamies
def scrape_FresquesZamies(soup, language):
    events = []
    for tag in soup.find_all("tr", class_="c10")[:3]:
        date_tag = tag.find("span", class_="c1")
        if not date_tag:
            continue
        date = dateparser.parse(date_tag.string).date()

        name_and_link = tag.find("a", class_="c21")
        if not name_and_link:
            continue

        events.append(
            (
                name_and_link.string,
                name_and_link.string,
                date,
                "Impact Hub Lausanne",
                name_and_link["href"],
                language,
            )
        )
    return events


# Fresque du Climat: we'll truncate to only the first three per language
def has_class_my3_only(tag):
    if not tag.name == "div":
        return False
    if not tag.has_attr("class"):
        return False
    classes = tag["class"]
    return len(classes) == 1 and classes[0] == "my-3"


def scrape_FresqueDuClimat(soup, title):
    events = []
    tag = soup.find(has_class_my3_only)
    max_count = 5
    if title != "Fresque du Climat":
        max_count = 3
    for child in tag.find_all("a", class_="text-decoration-none")[:max_count]:
        if child.get("href") == "":
            continue  # no URL, the workshop is fully booked
        url = "https://association.climatefresk.org" + child.get("href")

        child2 = child.find("div", class_="flex-grow-1")
        divs = child2.find_all("div")

        # date, hour, place
        child4 = divs[0].find("small", class_="text-secondary")
        x = child4.text.split("·")
        date_string = x[0].strip()
        date = dateparser.parse(date_string).date()
        place = re.sub(r"\s+", " ", x[2].strip())

        # title, language
        child5 = divs[1]
        spans = child5.find_all("span")
        name = spans[0].text
        language = spans[1].text
        if language == "(Deutsch)":
            language = "de"
        elif language == "(English)":
            language = "en"
        elif language == "(Français)":
            language = "fr"
        else:
            raise Exception("Language not handled: " + language)

        events.append((title, name, date, place, url, language))
    return events


def is_EventBrite_location(tag):
    return (
        tag.name == "div"
        and tag.has_attr("data-subcontent-key")
        and tag.attrs["data-subcontent-key"] == "location"
    )


# EventBrite
def scrape_EventBrite(soup, title):
    events = []
    for tag in soup.find_all("ul", class_="cc-card-list"):
        for card in tag.find_all("li", class_="cc-card-list__item"):
            child = card.find("h3", class_="eds-event-card-content__title")
            if not child:
                raise Exception("Title element not found")
            inner = child.find("div", class_="eds-is-hidden-accessible")
            if not inner:
                raise Exception("Title text not found")
            name = inner.text

            child = card.find("div", class_="eds-event-card-content__sub-title")
            if not child:
                raise Exception("Subtitle element for date not found")
            date = child.text

            child = card.find(is_EventBrite_location)
            if not child:
                if "EN LIGNE" in name.upper():
                    continue
                raise Exception("Location element not found:", card)
            place = child.text

            child = card.find("aside", class_="eds-event-card-content__image-container")
            if not child:
                raise Exception("Image element for URL not found")
            url = child.a.href

            events.append(
                (
                    title,
                    name,
                    date,
                    place,
                    url,
                    "fr",
                )
            )
    return events


# Given an array of events, filters for Switzerland and appends to each tuple the identified city.
# Input: array of (title, event name, date, place, url, language)
# Output: array of (title, event name, date, place, url, language, city)
def append_city_and_filter_for_switzerland(events, debug):
    normalizer = str.maketrans("ÜÈÂ", "UEA")
    cities = dict()
    for c in (
        "Bern",
        "Bienne",
        "Bulle",
        "Fribourg",
        "Genève",
        "Gland",
        "Lausanne",
        "Neuchâtel",
        "Nyon",
        "Rolle",
        "Sion",
        "St. Gallen",
        "Vevey",
        "Zürich",
    ):
        cities[c.upper().translate(normalizer)] = c
    filtered = []
    for event in events:
        name = event[1]
        place = event[3]
        normalized_place = place.upper().translate(normalizer)
        city = None
        for normalized_city, c in cities.items():
            if normalized_city in normalized_place:
                city = c
                break

        if not city:
            if "Fresque du Climat" in name:
                raise Exception("Missed Swiss city:", place, "(" + name + ")")
            if debug:
                print("Discarding, not in Switzerland:", place, "(" + name + ")")
            continue

        filtered.append(tuple([*list(event), city]))
    return filtered


# Given an array of events, build a dictionary with the cities and a list of events in each.
def group_events_by_city(events):
    # the main cities we care about and where enough events happen.
    # in a future version of this algorithm, we could derive this list from the events themselves.
    cities = ("Bern", "Genève", "Lausanne", "Zürich", "Zurich")

    # fill the dictionary
    grouped = dict()
    for event in events:
        city = event[6]
        if not city in grouped:
            grouped[city] = []
        grouped[city].append(event)

    # move all items that are in a single city, to a common empty key ''
    cities_to_delete = []
    lone_events = []
    for city, events in grouped.items():
        if len(events) < 2:
            cities_to_delete.append(city)
            lone_events.extend(events)
    for city in cities_to_delete:
        del grouped[city]
    grouped[""] = lone_events

    return grouped


# Adds a HTML table row (5 columns) for each event, as long as it appears to be in Switzerland.
# events: input array of tuples (workshop name, event name, date, place, url, language)
# f: file to write to
# debug: boolean, where to emit debug messages
def inject_events(events, f, debug):
    print(
        """
    <div class="tableCont">
        <table class="eventsTable">
        <thead>
            <tr>
            <td>Atelier</td>
            <td>Date</td>
            <td>Événement</td>
            <td>Lieu</td>
            <td>Lien</td>
            </tr>
        </thead>
        <tbody>
""",
        file=f,
    )

    for event in events:
        print("<tr>", file=f)
        print(
            "<td>",
            event[0],
            '<img src="flags/icons8-'
            + event[5]
            + '-16.png" alt="'
            + event[5]
            + '"/></td>',
            file=f,
        )
        print(
            "<td>", format_date(event[2], "EEEE d MMMM", locale="fr"), "</td>", file=f
        )
        print("<td>", event[1], "</td>", file=f)
        print("<td>", event[3], "</td>", file=f)
        print('<td><a href="', event[4], '">Billeterie</a></td>', file=f)
        print("</tr>", file=f)

    print(
        """
        </tbody>
        </table>
    </div>
""",
        file=f,
    )


# Add a HTML section for a given city
def inject_city(city, events, f, debug):
    if len(events) > 0:
        print("<h2>", city, "</h2>", file=f)
        inject_events(events, f, debug)


# Refreshes the file at "filename", if at least a day behind "today", with the contents at "url".
def refresh_cache(filename, today, url):
    try:
        ts = os.path.getmtime(filename)
    except OSError:
        ts = 0
    filetime = datetime.datetime.fromtimestamp(ts)
    delta = today - filetime
    if delta.days >= 1:
        print('Refreshing "' + filename + '" from ' + url + ", date was", filetime)

        if url.startswith("https://www.eventbrite.com/"):
            session = HTMLSession()
            r = session.get(url)
            r.html.render()  # this call executes the js in the page
            with open(filename, "w") as f:
                print(r.html.find("ul.cc-card-list", first=True).html, file=f)
        else:
            r = requests.get(url)
            with open(filename, "w") as f:
                print(r.text, file=f)


# write events as JSON
# TODO: replace event tuples in this code with dictionaries to begin with
def write_events_as_json(events, f):
    ae = []
    t = datetime.time(0, 0)
    for event in all_events:
        de = {
            KEY_TITLE: event[0],
            KEY_NAME: event[1],
            KEY_DATE: math.floor(datetime.datetime.combine(event[2], t).timestamp()),
            KEY_DATE_STRING: format_date(event[2], "EEEE d MMMM", locale="fr"),
            KEY_PLACE: event[3],
            KEY_URL: event[4],
            KEY_LANGUAGE: event[5],
            KEY_CITY: event[6],
            KEY_LINGUISTIC_REGION: "Deutschschweiz"
            if event[6] in ("Bern", "St. Gallen", "Zürich")
            else "Romandie",
        }
        ae.append(de)
    print("events=" + json.dumps(ae, indent=4), file=f)


# Main code starts here

# Parse the command-line flags.
argParser = argparse.ArgumentParser()
argParser.add_argument(
    "-c",
    "--cache_dir",
    default="cache",
    help="Directory where the HTML files are cached for 1 day to reduce host load.",
)
argParser.add_argument(
    "-o",
    "--output_html",
    default="/dev/null",
    help="Output HTML file to write, disabled if left empty.",
)
argParser.add_argument(
    "-d", "--debug", default=False, help="Whether to output debug information."
)
args = argParser.parse_args()

# Set up the list of calendars we are going to read.
# Each tuple is (workshop name, calendar URL).
calendars = [
    (
        "Fresque de la Mobilité",
        "https://www.billetweb.fr/multi_event.php?multi=11698",
        "fr",
    ),
    (
        "Fresque Océane",
        "https://www.billetweb.fr/multi_event.php?multi=15247",
        "fr",
    ),
    (
        "Fresque de l'Alimentation",
        "https://www.billetweb.fr/multi_event.php?multi=11155",
        "fr",
    ),
    (
        "Fresque de la Biodiversité",
        "https://www.billetweb.fr/multi_event.php?&multi=17309&margin=no_margin",
        "fr",
    ),
    (
        "Fresque du Numérique",
        "https://www.billetweb.fr/multi_event.php?multi=11442",
        "fr",
    ),
    (
        "Atelier Ogre",
        "https://www.billetweb.fr/multi_event.php?multi=13026",
        "fr",
    ),
    (
        "Digital Collage",
        "https://www.billetweb.fr/multi_event.php?multi=12991",
        "en",
    ),
    (
        "Fresque de l'Eau",
        "https://www.billetweb.fr/multi_event.php?multi=u138110&margin=no_margin",
        "fr",
    ),
    (
        "Fresque de la Construction",
        "https://www.billetweb.fr/multi_event.php?multi=11574",
        "fr",
    ),
    (
        "Fresques Zamies",
        "https://fresqueszamies.ch/",
        "fr",
    ),
    (
        "Fresque du Climat",
        "https://association.climatefresk.org/training_sessions/search_public_wp?utf8=%E2%9C%93&authenticity_token=jVbLQTo8m9BIByCiUa4xBSl6Zp%2FJW0lq7FgFbw7GpIllVKjduCbQ6SzRxkC4FpdQ4vWnLgVXp1jkLj0cK56mGQ%3D%3D&language=fr&tenant_token=36bd2274d3982262c0021755&user_input_autocomplete_address=&locality=&latitude=&longitude=&distance=100&country_filtering=206&categories%5B%5D=ATELIER&email=&commit=Valider&facilitation_languages%5B%5D=18",
        "fr",
    ),
    (
        "Climate Fresk",
        "https://association.climatefresk.org/training_sessions/search_public_wp?utf8=%E2%9C%93&authenticity_token=jVbLQTo8m9BIByCiUa4xBSl6Zp%2FJW0lq7FgFbw7GpIllVKjduCbQ6SzRxkC4FpdQ4vWnLgVXp1jkLj0cK56mGQ%3D%3D&language=fr&tenant_token=36bd2274d3982262c0021755&user_input_autocomplete_address=&locality=&latitude=&longitude=&distance=100&country_filtering=206&categories%5B%5D=ATELIER&email=&commit=Valider&facilitation_languages%5B%5D=3",
        "en",
    ),
    (
        "Climate Fresk",
        "https://association.climatefresk.org/training_sessions/search_public_wp?utf8=%E2%9C%93&authenticity_token=jVbLQTo8m9BIByCiUa4xBSl6Zp%2FJW0lq7FgFbw7GpIllVKjduCbQ6SzRxkC4FpdQ4vWnLgVXp1jkLj0cK56mGQ%3D%3D&language=fr&tenant_token=36bd2274d3982262c0021755&user_input_autocomplete_address=&locality=&latitude=&longitude=&distance=100&country_filtering=206&categories%5B%5D=ATELIER&email=&commit=Valider&facilitation_languages%5B%5D=2",
        "de",
    ),
    (
        "L'Affresco del Clima",
        "https://association.climatefresk.org/training_sessions/search_public_wp?utf8=%E2%9C%93&authenticity_token=jVbLQTo8m9BIByCiUa4xBSl6Zp%2FJW0lq7FgFbw7GpIllVKjduCbQ6SzRxkC4FpdQ4vWnLgVXp1jkLj0cK56mGQ%3D%3D&language=fr&tenant_token=36bd2274d3982262c0021755&user_input_autocomplete_address=&locality=&latitude=&longitude=&distance=100&country_filtering=206&categories%5B%5D=ATELIER&email=&commit=Valider&facilitation_languages%5B%5D=22",
        "it",
    ),
    (
        "Fresque des Nouveaux Récits",
        "https://www.billetweb.fr/multi_event.php?&multi=21617&view=list",
        "fr",
    ),
    (
        "Fresque Agri'Alim",
        "https://www.billetweb.fr/multi_event.php?multi=11421",
        "fr",
    ),
    (
        "Fresque du Sexisme",
        "https://www.billetweb.fr/multi_event.php?multi=21743&view=list",
        "fr",
    ),
    (
        "PSI (Puzzle des Solutions Individuelles Climat)",
        "https://www.billetweb.fr/multi_event.php?multi=21038",
        "fr",
    ),
    (
        "2tonnes",
        "https://www.eventbrite.com/cc/ateliers-grand-public-312309",
        "fr",
    ),
    (
        "Fresque du Plastique",
        "https://www.eventbrite.fr/o/la-fresque-du-plastique-45763194553",
        "fr",
    ),
]
calendars.sort(key=lambda c: c[0])  # sort by workshop name

# Prepare cache.
if not os.path.exists(args.cache_dir):
    os.mkdir(args.cache_dir)
today = datetime.datetime.today()

# Inject extra events we are aware of: (title, event name, date, place, url, language)
all_events = [
    (
        "2tonnes",
        "2tonnes",
        datetime.date(2023, 5, 4),
        "Impact Hub Lausanne",
        "https://my.weezevent.com/atelier-2-tonnes-world-a-lausanne",
        "fr",
    ),
    (
        "Circular Economy Collage",
        "Circular Economy Collage",
        datetime.date(2023, 3, 17),
        "ETH Zürich",
        "https://docs.google.com/forms/d/e/1FAIpQLSd5-uWcB8Ue9l1qTEIutwnfa7dDlWSodvCye_gNm3LVUucASg/viewform",
        "en",
    ),
    (
        "2tonnes",
        "2tonnes",
        datetime.date(2023, 3, 21),
        "Espace 3DD Genève",
        "https://www.eventbrite.com/e/billets-2tonnes-france-a-geneve-salon-open-geneva-en-francais-dates-multiple--570593950867?aff=odcleoeventsincollection&keep_tld=1",
        "fr",
    ),
    (
        "2tonnes",
        "2tonnes",
        datetime.date(2023, 3, 30),
        "Le Marronier - Maison de la Transition, Vevey",
        "https://www.eventbrite.com/e/billets-2tonnes-world-a-vevey-suisse-en-francais-dates-multiples--569573859747?aff=odcleoeventsincollection&keep_tld=1",
        "fr",
    ),
]
for calendar in calendars:
    title = calendar[0]
    url = calendar[1]
    language = calendar[2]

    # load and parse the file
    filename = os.path.join(args.cache_dir, title + "_" + language + ".html")
    refresh_cache(filename, today, url)
    with open(filename) as fp:
        soup = BeautifulSoup(fp, "html.parser")

    # scrape the events depending on the ticketing platform
    if url.startswith("https://www.billetweb.fr/"):
        events = scrape_BilletWeb(soup, title, language)
    elif url.startswith("https://fresqueszamies.ch/"):
        events = scrape_FresquesZamies(soup, language)
    elif url.startswith("https://association.climatefresk.org/"):
        events = scrape_FresqueDuClimat(soup, title)
    elif url.startswith("https://www.eventbrite."):
        events = scrape_EventBrite(soup, title)
    else:
        raise Exception("URL not handled: " + url)

    print_url = ""
    if len(events) == 0:
        print_url = "(" + url + ")"
    print(len(events), "scraped from", title, "(" + language + ")", print_url)
    all_events.extend(events)

count_parsed_events = len(all_events)
all_events = append_city_and_filter_for_switzerland(all_events, args.debug)
grouped = group_events_by_city(all_events)

# temporary as we replace date strings with actual Date objects
# TODO: remove this now that all parsers are now emitting dates
for event in all_events:
    if not isinstance(event[2], datetime.date):
        raise Exception("Not a date object:", event[2])

# TODO: replace with Mako templates or similar.
with open(args.output_html, "w") as f:
    print(
        """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <link rel="icon" href="/favicon.ico">
    <title>Ateliers zamis en Suisse</title>
    <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600&family=Hanken+Grotesk:wght@300;400;500&display=swap" rel="stylesheet">

    <style>
    :root {
        --accentcolor-1: #7ea656;
        --accentcolor-2: #820001;
        --accentcolor-1-light: #cedebf;
        --accentcolor-2-light: #e4c5c5;
        --fontfam-headings: "Hanken Grotesk", Arial, sans-serif;
        --fontfam-text: "Open Sans", Arial, sans-serif;
    }
        .cornerimg {
        position: fixed;
        top:0;
        right:0;
        width: min(45px, 20%);
        z-index: -1;
        }
        h1, h2 {
        font-family:var(--fontfam-headings);
        }
        h1 {
        font-size: 40px;
        }
        h2 {
        font-size: 30px;
        }
        p {
        font-family: var(--fontfam-headings);
        color: #323331;
        font-size:18px;
        }
        a {
        color: var(--accentcolor-2);
        transition: .2s ease;
        }
        a:hover {
        color: var(--accentcolor-1);
        }
        #.titleCont {
        #margin: 250px 0 100px;
        #}
        .titleCont h1 {
        color: var(--accentcolor-1);
        font-size: 40px;
        }
        .slogan {
        font-size: 22px;
        }
        .cont-column {
        width: min(100%, 1000px);
        margin:auto;
        }
        .tableCont {
        border: 1px solid #ddd;
        border-radius: 5px;
        }
        .eventsTable {
        border-collapse: collapse;
        width: 100%;
        }
        .eventsTable td {
        padding: 8px;
        font-family: var(--fontfam-text);
        }
        .eventsTable tr {
        transition: .3s ease;
        }
        .eventsTable tr:nth-child(even) {background-color: var(--accentcolor-1-light);}
        .hidden {
        visibility: hidden;
        }
        .eventsTable tr:hover span {
        visibility: visible;
        }
        .impactCont {
        width: 20%;
        margin:50px auto;
        text-align: center;
        }
        .impactCont img {
        width: 100%;
        }
    </style>
</head>
<body>
    <img class="cornerimg" src="images/image1.jpg" alt="globe" />
    <section class="cont-column">
    <div class="titleCont">
        <h1>Ateliers zamis en Suisse</h1>
        <p>Cette page répertorie les ateliers en présentiel en Suisse prévus prochainement.</p>
    </div>
    <div id="event_container">
""",
        file=f,
    )

    for city in sorted(grouped):
        if city != "":
            inject_city(city, grouped[city], f, args.debug)
    inject_city("Ailleurs", grouped[""], f, args.debug)

    print(
        """
    </div>
    <p>Calendrier lus, entre autres:<ul>
""",
        file=f,
    )
    for calendar in calendars:
        print('<li><a href="' + calendar[1] + '">', calendar[0], "</a></li>", file=f)
    print(
        """
    </ul></p>
    <p>Pour une liste encore plus large d'ateliers existants, voir <a href="https://fresqueduclimat.org/wiki/index.php?title=Les_fresques_amies">la liste des fresques amies</a>.</p>
    <p>Pour toute question, suggestion ou bug (par exemple, un lien est cassé, ou un événement en Suisse dans un des calendriers n'est pas répertorié sur cette page), merci de contacter <a href="mailto:jeffrey@theshifters.ch" target="_blank">jeffrey@theshifters.ch</a>.</p>
    <p>Les icônes du <a target="_blank" href="https://icons8.com/icon/u5e279g2v-R8/france">drapeau de France</a> et autres pays sont mis à disposition par <a target="_blank" href="https://icons8.com">Icons8</a>.</p>
""",
        file=f,
    )
    print(
        '<span style="display:none" id = "initialDate">'
        + format_date(today, "MM/dd/yyyy", locale="en")
        + "</span>",
        file=f,
    )
    print(
        '<span style="display:none" id = "initialTime">'
        + str(math.floor(datetime.datetime.timestamp(datetime.datetime.now())))
        + "</span>",
        file=f,
    )
    print(
        """
    <p>Dernière mise à jour: <span id="dateDiffHere">il y a un certain temps</span>.</p>
    </section>
</body>
<script>
""",
        file=f,
    )
    write_events_as_json(all_events, f)
    print(
        """
// NOTE: this code ignores time zones.
let inputInitialDate = document.getElementById("initialDate").innerHTML;
const initialDate = new Date(inputInitialDate);
let inputInitialTime = document.getElementById("initialTime").innerHTML;
const initialTime = new Date(parseInt(inputInitialTime) * 1000)
const nowDate = new Date();
var diffTime = Math.abs(nowDate - initialTime);
var diffMinutes = Math.floor(diffTime / (60 * 1000));
if (diffMinutes < 2) {
  t = "à l'instant"
} else if (diffMinutes < 60) {
  t = "il y a " + diffMinutes + " minutes"
} else {
  var diffHours = Math.floor(diffMinutes / 60);
  if (diffHours == 1) {
    t = "il y a une heure"
  } else if (diffHours < 24) {
    t = "il y a " + diffHours + " heures"
  } else {
    var diffDays = Math.floor(diffHours / 24);
    if (diffDays == 1 ) {
      t = "hier"
    } else {
      t = "il y a " + diffDays + " jours"
    }
  }
}
document.getElementById("dateDiffHere").innerHTML = t;

// Event formatting starts here

let today = nowDate.setHours(0, 0, 0, 0);

function displayDate(timestamp_sec, date_string) {
  let then = new Date(timestamp_sec * 1000)
  let diff = (then - today) / (1000 * 60 * 60 * 24)
  if (diff == 0) {
    return "aujourd'hui"
  } else if (diff == 1) {
    return 'demain'
  } else if (diff < 7) {
    return 'dans ' + diff + ' jours'
  } else {
    return date_string
  }
}

function injectTable(region, events) {
  t = '<h2>' + region + '</h2>'
  t += '<div class="tableCont"><table class="eventsTable">'
  t += '<thead><tr><td>Atelier</td><td>Date</td><td>Événement</td><td>Lieu</td><td>Lien</td></tr></thead>'
  t += '<tbody>'
  events.sort(function(a, b){return a.date - b.date});
  for (let x in events) {
    var event = events[x]
    t += '<tr>'
    t += '<td>' + event.title + ' <img src="./flags/icons8-' + event.language + '-16.png" alt="' + event.language + '"></td>'
    t += '<td>' + displayDate(event.date, event.date_string) + '</td>'
    t += '<td>' + event.name + '</td>'
    t += '<td>' + event.city + '<br><span class="hidden">' + event.place + '</span></td>'
    t += '<td><a href="'+ event.url +'">Billeterie</a></td>'
    t += '</tr>'
  }
  t += '</tbody></table></div>'
  document.getElementById("event_container").innerHTML += t
}

function eventIsInTheFuture(event) {
  return (event.date * 1000) >= today;
}

document.getElementById("event_container").innerHTML = ''
const lregions = new Set();
events = events.filter(eventIsInTheFuture)
for (let x in events) {
  var event = events[x]
  lregions.add(event.lregion)
}
lregions.forEach(function(lregion) {
  const filtered = events.filter(myFunction);
  function myFunction(event) {
    return event.lregion == lregion;
  }
  injectTable(lregion, filtered)
})

</script>
</html>
""",
        file=f,
    )


print(
    "Wrote",
    len(all_events),
    "events to",
    args.output_html,
    "after parsing",
    count_parsed_events,
    "events from",
    len(calendars),
    "calendars.",
)
