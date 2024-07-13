#!/usr/bin/env python3

# pyright: reportUnknownVariableType=false
import json
import os
from typing import assert_never
from urllib import error, request
from urllib.error import HTTPError
from urllib.request import Request
from http.client import HTTPResponse
from datetime import datetime

from helper import Logger

HOME = os.path.expanduser("~")
CONFIG_FILE = "%s/.config/convas/config" % HOME


def get_paginated_responses(url: str, headers: dict[str, str]) -> list[str] | None:
    next_page: str = url
    data: list[str] = []
    while next_page:
        req: Request = Request(next_page, headers=headers)
        try:
            response: HTTPResponse = request.urlopen(req)
        except HTTPError as e:
            Logger.info(f"Error fetching data: {e}")
            return
        status_code: int = response.getcode()
        if status_code == 404:
            return None
        elif status_code != 200:
            print(f"Error fetching data: {status_code}")
            exit()

        response_data: dict[str, str] = json.loads(response.read().decode("utf-8"))
        data.extend(response_data)

        res_h = response.getheaders()
        response.close()
        for header in res_h:
            if header[0] == "link":
                links = header[1]
                links = links.split(",")
                current_page = ""
                last_page = ""
                for link in links:
                    link = link.split(";")
                    is_next = link[1].split("=")
                    if is_next[1] == '"current"':
                        current_page = link[0].strip().strip("<>")
                    if is_next[1] == '"next"':
                        next_page = link[0].strip("<>")
                    if is_next[1] == '"last"':
                        last_page = link[0].strip("<>")
                        if current_page == last_page:
                            return data
                break
    return data


def get_course_names(json_obj: list[dict[str, str]]) -> list[str]:
    return [course["name"] for course in json_obj]


def get_current_courses(json_obj: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        course
        for course in json_obj
        if course["term"]["name"] == json_obj[-1]["term"]["name"]
    ]


def get_discussions(assignments: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        discussion
        for discussion in assignments
        if "submission_type" in discussion.keys()
        and "discussion_topic" in discussion["submission_type"]
    ]


def get_current_course_names(json_obj: list[dict[str, str]]) -> list[str]:
    return [
        course["course_code"]
        for course in json_obj
        if course["term"]["name"] == json_obj[-1]["term"]["name"]
    ]


def get_current_course_name_id_map(json_obj: list[dict[str, str]]) -> dict[str, str]:
    return {
        course["name"]: course["id"]
        for course in json_obj
        if course["term"]["name"] == json_obj[-1]["term"]["name"]
    }


def get_current_course_id(json_obj: list[dict[str, str]]) -> list[str]:
    return [
        course["id"]
        for course in json_obj
        if course["term"]["name"] == json_obj[-1]["term"]["name"]
    ]


def get_request(url: str, request_headers: dict[str, str]) -> HTTPResponse:
    res: HTTPResponse = request.urlopen(url, headers=request_headers)
    assert isinstance(res, HTTPResponse)
    return res


def get_todo_items(
    url: str, headers: dict[str, str], course_id: int
) -> list[str] | None:
    req: list[str] = request.urlopen(f"{url}/{course_id}/todo", headers=headers)
    return req


def get_course_info(url: str, headers: dict):
    courses = get_paginated_responses(
        f"{url}?per_page=60&enrollment_type=student&include[]=syllabus_body&include[]=total_scores&include[]=public_description&include[]=course_progress&include[]=sections&include[]=teachers&include[]=term&include[]=favorites",
        headers,
    )
    return courses


def get_quizzes(url: str, headers: dict[str, str], course_id: int) -> list[str] | None:
    quizzes = get_paginated_responses(f"{url}/{course_id}/quizzes", headers=headers)
    return quizzes


def get_files(url: str, headers: dict[str, str], course_id: int) -> list[str] | None:
    files = get_paginated_responses(f"{url}{course_id}/files", headers)
    return files


def download_file(
    url: str, id: int, course_id: int, outfile: str, headers: dict[str, str]
) -> bool:
    try:
        with request.urlopen(url) as response:
            with open(outfile, "wb") as out_file:
                out_file.write(response.read())
                return True
    except error.URLError as err:
        Logger.info(f"Failed to download file. Exception {err}")
        return False


def get_assignments_request(url: str, headers: dict[str, str], course_id: int):
    assignments = get_paginated_responses(
        f"{url}/courses/{course_id}/assignments", headers
    )
    return assignments


def get_announcements_request(
    url: str, headers: dict[str, str], course_id: list[str] | str, start_date: str
):
    if isinstance(course_id, str):
        current_timestamp = datetime.now().strftime("%Y:%m:%d")
        announcements: list[dict[str, str]] = get_paginated_responses(
            f"{url}/announcements?context_codes[]=course_{course_id}&start_date={start_date}&end_date={current_timestamp}"
        )
    elif isinstance(course_id, list):
        query_params = ""
        for course in course_id:
            query_params += f"context_codes[]=course_{course}&"
        query_params += f"start_date={start_date}"
        announcements = get_paginated_responses(
            f"{url}/announcements?{query_params}", headers
        )
    return announcements


def get_files_request(url: str, headers: dict[str, str], course_id: int):
    files = get_paginated_responses(f"{url}/courses/{course_id}/files", headers)
    return files


def get_quizzes_request(url: str, headers: dict[str, str], course_id: int):
    quizzes = get_paginated_responses(f"{url}/courses/{course_id}/quizzes", headers)
    return quizzes
