import os
import re

import numpy as np
import pandas as pd
from tqdm import tqdm

INPUT_DIR = "input/"
OUTPUT_DIR = "output/"

# 由于收到的文件，起始行各不相同，且其中有多页文件，难以手动调整，故用字典记录
HEADER_DICT = {'盾勇': 0, 'WOG-text-20230711': 1, '검과 마법_스크립트': 1, '열강글로벌 최신언어팩 221205': 1}

# 列名对应关系
# 语言支持：https://cloud.google.com/translate/docs/languages?hl=zh-cn
RENAME_DICT_ALL = {"zh-CN": "zh-CN", "zh-TW": "zh-TW", "en": "en", "th": "th", "id": "id", "ja": "ja", "ko": "ko",
                   "ru": "ru", "pt": "pt", "vi": "vi",  # 保持不变的列表名
                   "cs": "zh-CN", "ct": "zh-TW", "ind": "id", "kr": "ko", "jp": "ja",  # WOG-text-20230711,검과 마법_스크립트
                   "中文对应信息（语言1）": "zh-CN", "英文对应信息（语言2）": "en", "泰文对应信息（语言3）": "th",
                   "繁体对应信息（语言4）": "zh-TW", "葡语对应信息（语言4）": "pt", "印尼语": "id",  # excelWord.xlsx
                   "中文": "zh-CN", "英文": "en", "泰文": "th",
                   "繁体": "zh-TW", "韩文": "ko", "葡语": "pt", "印尼": "id",  # layers_widgets.xlsx
                   "Japanese": "ja", "EN 正确英文": "en", "CN 对应中文": "zh-CN",  # 固有名詞リスト（英語）full(2).xlsx
                   "en-US": "en", "日语": "ja",  # [방패] 용어집(중, 영) 盾勇术语表-有部分日语.xlsx
                   }


# 单元格操作
def cell_process(text: str):
    # 正则匹配替换
    replace_patterns = {
        # 特殊
        r"#N/A": "",  # 盾勇
        #  通用
        "\"": "",  # 去掉双引号
    }
    for pattern, replacement in replace_patterns.items():
        text = re.sub(pattern, replacement, text)

    return text.strip()


# 对于
def clean_merge_save_excel_files(input_path: str, output_path: str) -> None:
    print("\nstart cleaning, merging and saving excel files.")
    for dir_path, dir_names, file_names in os.walk(input_path):
        for file_name in tqdm(file_names, desc=dir_path):
            if file_name.endswith(".xlsx"):
                # get file path
                file_path = os.path.join(dir_path, file_name)
                # get header beginning row
                folder_name = os.path.basename(dir_path)
                header_row = HEADER_DICT.get(folder_name, 0)
                # read all sheets into dataframe list
                xls = pd.ExcelFile(file_path, engine='openpyxl')
                df_list = [xls.parse(sheet_name, header=header_row) for sheet_name in xls.sheet_names]
                # merge dataframes into one
                df_merged = pd.concat(df_list, axis=0, ignore_index=True)
                # rename columns
                rename_columns_dict = {k: v for k, v in RENAME_DICT_ALL.items() if k in df_merged.columns}
                df_merged.rename(columns=rename_columns_dict, inplace=True)
                df_merged = df_merged[rename_columns_dict.values()]

                # replace np.nan with None
                df_merged = df_merged.replace(np.nan, None)
                # Clean the text in the dataframe
                df_merged = df_merged.apply(lambda row: row.apply(
                    lambda cell: cell if isinstance(cell, int) or cell is None else cell_process(str(cell))), axis=1)

                # combine the output file path
                output_file = re.sub(input_path, output_path, file_path)
                output_directory = os.path.dirname(output_file)
                # create directory
                os.makedirs(output_directory, exist_ok=True)
                # save
                df_merged.to_excel(output_file, index=False)


def merge_and_save_all_excel_files(input_path: str) -> None:
    print("\nstart merging all excel files into one.")
    df_all = pd.DataFrame()
    for dir_path, dir_names, file_names in os.walk(input_path):
        for file_name in tqdm(file_names, desc=dir_path):
            if file_name.endswith(".xlsx"):
                if file_name.endswith(".xlsx"):
                    file_path = os.path.join(dir_path, file_name)
                    df = pd.read_excel(file_path)
                    df = df.replace(np.nan, None)  # replace np.nan with None
                    df["source"] = file_name  # tag the source file
                    df_all = pd.concat([df_all, df], axis=0, ignore_index=True)
    # move column "source" to the end
    df_all["source"] = df_all.pop("source")
    # excel文件输出
    df_all.to_excel(os.path.join(input_path, "../all_files_merged.xlsx"), index=False)
    # csv文件输出
    df_all.to_csv(os.path.join(input_path, "../all_files_merged.csv"), index=False)
    # csv文件输出
    df_all = df_all.drop("source", axis=1)  # delete the "source" column
    language_list = df_all.columns.tolist()
    language_pairs = [[x, y] for x in language_list for y in language_list if x != y]
    for pair in language_pairs:
        data = df_all[pair]
        data = data.dropna(how='any')  # clear all rows include nan
        data = data.drop_duplicates()  # delete exactly the same rows
        # filter the empty language pairs
        if len(data) > 0:
            file_name = os.path.join(input_path, "all_files_merged_{0}_{1}.csv".format(pair[0], pair[1]))
            data.to_csv(file_name, index=False)


if __name__ == "__main__":
    clean_merge_save_excel_files(INPUT_DIR, OUTPUT_DIR)
    merge_and_save_all_excel_files(OUTPUT_DIR)
