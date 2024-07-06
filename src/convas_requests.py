#!/usr/bin/env python3

import json
import os
from urllib import error, request
from urllib.request import Request
from http.client import HTTPResponse

from helper import Logger

HOME = os.path.expanduser("~")
CONFIG_FILE = "%s/.config/convas/config" % HOME


def get_paginated_responses(url: str, headers: dict[str, str]) -> list[str] | None:
    next_page: str = url
    data: list[str] = []
    while next_page:
        req: Request = Request(url, headers=headers)
        response = request.urlopen(req)
        status_code: int = response.getcode()
        if status_code == 404:
            return None
        elif status_code != 200:
            print(f"Error: {status_code}")
            return None
        response_data: str = response.read().decode("utf-8")
        response.close()
        data.extend(response_data)
        next_page = response.links.get("next", {}).get("url")

    return data


def get_course_names(json_obj) -> list[str]:
    return [course["name"] for course in json_obj]


def get_current_courses(json_obj) -> list[dict[str, str]]:
    return [
        course
        for course in json_obj
        if course["created_at"][:10] == json_obj[-1]["created_at"][:10]
    ]


def get_discussions(assignments: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        discussion
        for discussion in assignments
        if "submission_type" in discussion.keys()
        and "discussion_topic" in discussion["submission_type"]
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


def download_file(
    url: str, id: int, course_id: int, outfile: str, headers: dict[str, str]
) -> bool:
    try:
        response = HTTPResponse | None
        with request.urlopen(url) as response:
            with open(outfile, "wb") as out_file:
                out_file.write(response.read())
                return True
    except error.URLError as err:
        Logger.info(f"Failed to download file. Exception {err}")
        return False


def get_assignments_request(url, headers, course_id: int):
    print("Getting assignments for %s" % course_id, end="\n")
    assignments = get_paginated_responses(f"{url}/{course_id}/assignments", headers)
    with open(f"assignments{course_id}.json", "w") as file:
        json.dump(assignments, file)
    return assignments


with open("data.json") as file:
    data = file.read()
    all_courses = json.loads(data)
