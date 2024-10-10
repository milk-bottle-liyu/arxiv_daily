import datetime
import pandas as pd
import requests
import json
import arxiv
import os

base_url = "https://arxiv.paperswithcode.com/api/v0/papers/"


def get_authors(authors, first_author=False):
    output = str()
    if first_author == False:
        output = ", ".join(str(author) for author in authors)
    else:
        output = authors[0]
    return output


def sort_papers(papers):
    output = dict()
    keys = list(papers.keys())
    keys.sort(reverse=True)
    for key in keys:
        output[key] = papers[key]
    return output


def get_daily_papers(topic, query="slam", max_results=2, last_date=None):
    """
    @param topic: str
    @param query: str
    @return paper_with_code: dict
    """

    # output 
    content = dict()
    content_to_web = dict()

    # content
    output = dict()

    client = arxiv.Client(
        delay_seconds=1
    )
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    results = client.results(search)

    cnt = 0
    new_last_date = None
    for result in results:
        paper_id = result.get_short_id()
        paper_title = result.title
        paper_url = result.entry_id
        code_url = base_url + paper_id
        paper_abstract = result.summary.replace("\n", " ")
        paper_authors = get_authors(result.authors)
        paper_first_author = get_authors(result.authors, first_author=True)
        primary_category = result.primary_category
        publish_time = result.published.date()
        update_time = result.updated.date()
        comments = result.comment

        if new_last_date is None:
            new_last_date = update_time
        if last_date is not None and update_time < last_date:
            break


        print("Time = ", update_time,
              " title = ", paper_title,
              " author = ", paper_first_author)

        # eg: 2108.09112v1 -> 2108.09112
        ver_pos = paper_id.find('v')
        if ver_pos == -1:
            paper_key = paper_id
        else:
            paper_key = paper_id[0:ver_pos]

        try:
            r = requests.get(code_url).json()
            # source code link
            if "official" in r and r["official"]:
                cnt += 1
                repo_url = r["official"]["url"]
                content[
                    paper_id] = {
                    "value": f"|**{update_time}**|**{paper_title}**|{paper_first_author} et.al.|[{paper_id}]({paper_url})|**[link]({repo_url})**|",
                    "finished": False
                }
                content_to_web[
                    paper_key] = f"- {update_time}, **{paper_title}**, {paper_first_author} et.al., Paper: [{paper_url}]({paper_url}), Code: **[{repo_url}]({repo_url})**"

            else:
                content[
                    paper_id] = {
                    "value": f"|**{update_time}**|**{paper_title}**|{paper_first_author} et.al.|[{paper_id}]({paper_url})|null|",
                    "finished": False
                }
                content_to_web[
                    paper_key] = f"- {update_time}, **{paper_title}**, {paper_first_author} et.al., Paper: [{paper_url}]({paper_url})"

            # TODO: select useful comments
            comments = None
            if comments != None:
                content_to_web[paper_key] = content_to_web[paper_key] + f", {comments}\n"
            else:
                content_to_web[paper_key] = content_to_web[paper_key] + f"\n"

        except Exception as e:
            print(f"exception: {e} with id: {paper_key}")
    content['update_date'] = new_last_date
    data = {topic: content}
    data_web = {topic: content_to_web}
    return data, data_web


def update_json_file(filename, data_all):
    with open(filename, "r") as f:
        content = f.read()
        if not content:
            m = {}
        else:
            m = json.loads(content)

    json_data = m.copy()

    # update papers in each keywords
    max_update_time = None
    for data in data_all:
        for keyword in data.keys():
            papers = data[keyword]
            last_date = papers.pop("update_date")
            if max_update_time is None:
                max_update_time = last_date
            else:
                if max_update_time < last_date:
                    max_update_time = last_date

            if keyword in json_data.keys():
                for paper_id in papers.keys():
                    if paper_id not in json_data[keyword]:
                        json_data[keyword][paper_id] = papers[paper_id]
            else:
                json_data[keyword] = papers

    json_data['update_date'] = max_update_time.strftime("%Y%m%d")
    with open(filename, "w") as f:
        json.dump(json_data, f, indent=4)


def json_to_md(filename, md_filename, to_web=False, use_title=True):
    """
    @param filename: str
    @param md_filename: str
    @return None
    """

    DateNow = datetime.date.today()
    DateNow = str(DateNow)
    DateNow = DateNow.replace('-', '.')

    with open(filename, "r") as f:
        content = f.read()
        if not content:
            data = {}
        else:
            data = json.loads(content)
        data.pop("update_date")

    # clean README.md if daily already exist else create it
    with open(md_filename, "w+") as f:
        pass

    # write data into README.md
    with open(md_filename, "w", encoding='utf8') as f:

        if (use_title == True) and (to_web == True):
            f.write("---\n" + "layout: default\n" + "---\n\n")

        if use_title == True:
            f.write("## Updated on " + DateNow + "\n\n")
        else:
            f.write("> Updated on " + DateNow + "\n\n")

        for keyword in data.keys():
            day_content = data[keyword]
            if not day_content:
                continue
            # the head of each part
            f.write(f"## {keyword}\n\n")

            if use_title == True:
                if to_web == False:
                    f.write("|Publish Date|Title|Authors|PDF|Code|Finish|\n" + "|---|---|---|---|---|---|\n")
                else:
                    f.write("| Publish Date | Title | Authors | PDF | Code |Finish|\n")
                    f.write("|:---------|:-----------------------|:---------|:------|:------|:------|\n")

            # sort papers by date
            day_content = sort_papers(day_content)

            for _, v in day_content.items():
                if v is not None:
                    f.write(v['value'])

                finished = day_content.get("finish", False)
                if finished:
                    f.write("**&check;**|\n")
                else:
                    f.write("**&cross;**|\n")

            f.write(f"\n")

    print("finished")

def make_pdf_link(value):
    link_name, link_value = value.split("](")
    link_name = link_name[1:]
    link_value = link_value[:-1]
    return '=HYPERLINK("%s", "%s")' % (link_value, link_name)


def make_code_link(value):
    link_name, link_value = value[2:-2].split("](")
    link_name = link_name[1:]
    link_value = link_value[:-1]
    return '=HYPERLINK("%s", "%s")' % (link_value, link_name)

def json_to_excel(json_file, excel_fold_name):
    with open(json_file, 'r', encoding='utf8') as fp:
        json_data = json.load(fp)

    for topic, content in json_data.items():
        content_dict = {
            "Publish Date": [],
            "Title": [],
            "Authors": [],
            "PDF": [],
            "Code": [],
            "Finish": []
        }
        if topic == 'update_date':
            continue
        paper_content_list = []
        for paper_id, paper_content in content.items():
            paper_content_list.append([paper_content['value'][1:-1].split('|'), paper_content['finished']])
        paper_content_list.sort(key=lambda x: int(x[0][0][2:-2].replace('-', '')), reverse=True)

        for parsed_value, finished in paper_content_list:
            content_dict["Publish Date"].append(parsed_value[0][2:-2])
            content_dict["Title"].append(parsed_value[1][2:-2])
            content_dict["Authors"].append(parsed_value[2])
            content_dict["PDF"].append(make_pdf_link(parsed_value[3]))
            content_dict["Code"].append(make_code_link(parsed_value[4]) if parsed_value[4] != 'null' else '')
            content_dict["Finish"].append(finished)

        df = pd.DataFrame.from_dict(content_dict)
        df.to_excel(os.path.join(excel_fold_name, f'{topic}.xlsx'), index=False)


if __name__ == "__main__":
    json_file = "cv-arxiv-daily.json"
    with open(json_file, 'r') as fp:
        try:
            last_date = json.load(fp).get('update_date', None)
        except:
            last_date = None
        if last_date is not None:
            last_date = datetime.datetime.strptime(last_date, "%Y%m%d").date()

    data_collector = []
    data_collector_web = []

    keywords = dict()
    keywords["LLM4AD"] = 'all:LLM AND all:"autonomous driving"'

    for topic, keyword in keywords.items():
        # topic = keyword.replace("\"","")
        print("Keyword: " + topic)

        data, data_web = get_daily_papers(topic, query=keyword, max_results=None, last_date=last_date)
        data_collector.append(data)
        data_collector_web.append(data_web)

        print("\n")

    # 1. update README.md file

    md_file = "README.md"
    # update json data
    update_json_file(json_file, data_collector)
    # json data to markdown
    # json_to_md(json_file, md_file)

    # 2. update topic.xlsx data
    excel_fold_name = 'llm4ad'
    json_to_excel(json_file, excel_fold_name)

    # # 2. update docs/index.md file
    # json_file = "./docs/cv-arxiv-daily-web.json"
    # md_file   = "./docs/index.md"
    # # update json data
    # update_json_file(json_file,data_collector)
    # # json data to markdown
    # json_to_md(json_file, md_file, to_web = True)
    #
    # # 3. Update docs/wechat.md file
    # json_file = "./docs/cv-arxiv-daily-wechat.json"
    # md_file   = "./docs/wechat.md"
    # # update json data
    # update_json_file(json_file, data_collector_web)
    # # json data to markdown
    # json_to_md(json_file, md_file, to_web=False, use_title= False)
