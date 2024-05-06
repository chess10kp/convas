
#!/usr/bin/env python3

import curses
import json
import os
import re
import subprocess
import time
from collections import namedtuple
from curses import panel, wrapper
from json import loads
from typing import Dict, Generator, Tuple
from enum import Enum
from urllib import error, request

HOME = os.path.expanduser("~")
CONFIG_FILE = "%s/.config/convas/config" % HOME


def get_paginated_responses(url, headers) -> list[str] | None:
    next_page = url
    data = []
    while next_page:
        response = request.urlopen(next_page, headers=headers)
        if response.status_code == 404:
            return None
        elif response.status_code != 200:
            print(f"Error: {response.status_code}")
            return None
        response_data = response.read().decode("utf-8")
        response.close()
        data.extend(response_data)
        next_page = response.links.get("next", {}).get("url")

    return data


def get_course_names(json_obj) -> list[str]:
    return [course["name"] for course in json_obj]


def get_current_courses(json_obj) -> list[Dict[str, str]]:
    return [
        course
        for course in json_obj
        if course["created_at"][:10] == json_obj[-1]["created_at"][:10]
    ]


def get_current_course_names(json_obj) -> list[str]:
    return [
        course["course_code"]
        for course in json_obj
        if course["created_at"][:10] == json_obj[-1]["created_at"][:10]
    ]


def get_current_course_name_id_map(json_obj) -> dict[str, str]:
    return {
        course["name"]: course["id"]
        for course in json_obj
        if course["created_at"][:10] == json_obj[-1]["created_at"][:10]
    }


def get_current_course_id(json_obj) -> list[str]:
    return [
        course["id"]
        for course in json_obj
        if course["created_at"][:10] == json_obj[-1]["created_at"][:10]
    ]


def get_request(url, headers):
    return request.urlopen(url, headers=headers)


def get_todo_items(url, headers, course_id: int):
    return request.urlopen(f"{url}/{course_id}/todo", headers=headers)


def get_quizzes(url: str, headers, course_id: int):
    quizzes = get_paginated_responses(f"{url}/{course_id}/quizzes", headers=headers)
    return quizzes


def get_files(url: str, headers, course_id: int):
    files = get_paginated_responses(f"{url}/{course_id}/files", headers)
    return files


def get_file_names(file_obj) -> list[str]:
    return [file["display_name"] for file in file_obj]


def get_file_download(file_obj) -> list[str]:
    return [file["url"] for file in file_obj]


def get_file_names_download(file_obj):
    return {file["display_name"]: file["url"] for file in file_obj}


def get_assignments_request(url, headers, course_id: int):
    print("Getting assignments for %s" % course_id, end="\n")
    assignments = get_paginated_responses(f"{url}/{course_id}/assignments", headers)
    with open(f"assignments{course_id}.json", "w") as file:
        json.dump(assignments, file)
    return assignments


with open("data.json") as file:
    data = file.read()
    all_courses = json.loads(data)
