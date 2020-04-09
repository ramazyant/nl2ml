import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
import copy

#################################################################################################################
#----------------------------------------------- BLOCK PROCESSING ----------------------------------------------#
#################################################################################################################

def closest_tag (code_block, tag_arr, pos):
    closest = -1
    for i in range(len(tag_arr) - 1):
        if (tag_arr[i] < code_block and tag_arr[i + 1] > code_block):
            closest = i
            break
    if pos == 'end':
        closest += 1
    return tag_arr[closest]

def tag_preproc(tag_arr):
    for i in range(len(tag_arr)):
        tag_arr[i] = tag_arr[i].lower()
        tag_arr[i] = re.sub(r'[^a-z0-9\s]', '', tag_arr[i])
        # tag_arr[i] = tag_arr[i].replace(' ', '_') #   ????????????
        try:
            if tag_arr[i][0] == ' ':
                tag_arr[i][0] = ''
        except:
            pass

def block_preproc(blocks_arr, key, block_type):
    if block_type == 'code':
        too_many_ns = r'\\n' * 10
        for i in range(len(blocks_arr)):
            if too_many_ns in blocks_arr[i]:
                blocks_arr[i] = ''
    elif block_type == 'tag':
        for i in range(len(blocks_arr)):
            if 'https://' in blocks_arr[i]:
                if i == 0:
                    for j in range(i, len(blocks_arr)):
                        if 'https://' in blocks_arr[j]:
                            continue
                        else:
                            blocks_arr[i] = blocks_arr[j]
                            break
                else:
                    blocks_arr[i] = blocks_arr[i - 1]

    for i in range(len(blocks_arr)):
        blocks_arr[i] = re.sub(r'\\\\\\u0022|\\u0027', "'", blocks_arr[i])
        blocks_arr[i] = re.sub(r'\\u00..', '', blocks_arr[i])
        blocks_arr[i] = re.sub(r'\\\\n', '\n', blocks_arr[i])
        blocks_arr[i] = re.sub(r'\\', '', blocks_arr[i])
        blocks_arr[i] = re.sub(key, '', blocks_arr[i])
        if block_type == 'tag':
            blocks_arr[i] = blocks_arr[i].lower()
            blocks_arr[i] = re.sub(r'[^a-z0-9\s]', '', blocks_arr[i])
            # blocks_arr[i] = blocks_arr[i].replace(' ', '_') #   ????????????


def comment_finder(text):
    comments = []
    line_end = [i for i in range(len(text)) if text.startswith('\n', i)]
    try:
        if text[0] == '#':          # text is non-empty by the condition before running
            comments.append(text[0:line_end[0]])
    except: #let's add a try-pass in case there is a code block with just 1 comment
        pass
    comments_begin = [(i + 1) for i in range(len(text)) if text.startswith('\n#', i)]
    comments_end = []
    try:
        for i in range(len(comments_begin)):
            comments_end.append(closest_tag(comments_begin[i], line_end, pos='end'))
    except:
        pass

    try:
        for i in range(len(comments_begin)):
            comments.append(text[comments_begin[i] : comments_end[i]])
    except:
        pass

    no_preproc = copy.deepcopy(comments)
    tag_preproc(comments)
    return comments, no_preproc

#################################################################################################################
#----------------------------------------------- NOTEBOOK PARSING ----------------------------------------------#
#################################################################################################################

# key_begin = r'cell_type : code '     # \ cell_type\ :\ code\ ,\ source\ :         
# key_end = r'execution_count :'       #null,\ outputs\ :[]"
def notebook_parse (link):
    key_begin = r'\u0022cell_type\u0022:\u0022code\u0022,\u0022source\u0022:'
    key_end = r'\u0022execution_count\u0022:null,\u0022outputs\u0022:[]'

    tag_key_begin = r'\u0022cell_type\u0022:\u0022markdown\u0022,\u0022source\u0022:'
    tag_key_end = r'},{\u0022metadata\u0022:{'

    r = requests.get('https://www.kaggle.com/' + link) # 'https://www.kaggle.com/roshansharma/amazon-alexa-reviews'

    soup = BeautifulSoup(r.text, 'html.parser')
    scripts = soup.find_all('script')

    blocks = []
    tags = []

    for scr in scripts:
        test_str = scr.text

        if (key_begin in test_str) and (key_end in test_str):
            #   finding code blocks ---------------------------------------
            res_begin = [i for i in range(len(test_str)) if test_str.startswith(key_begin, i)] 
            res_end = [i for i in range(len(test_str)) if test_str.startswith(key_end, i)]

            try:
                for i in range(min(len(res_begin), len(res_end))):
                    blocks.append(test_str[res_begin[i] : res_end[i]])
            except:
                pass

            blocks = list(dict.fromkeys(blocks))
            length = len(blocks)
            res_begin = res_begin[:length]
            res_end = res_end[:length]
            #   finding tags ---------------------------------------
            tags_begin_ = [i for i in range(res_end[-1]) if test_str.startswith(tag_key_begin, i)]
            
            tags_begin = []
            try:
                for i in range(len(res_begin)):
                    tags_begin.append(closest_tag(res_begin[i], tags_begin_, pos = 'begin'))
            except:
                pass

            tags_end_ = [i for i in range(res_end[-1]) if test_str.startswith(tag_key_end, i)]
            
            tags_end = []
            try:
                for i in range(len(tags_begin)):
                    tags_end.append(closest_tag(tags_begin[i], tags_end_, pos='end'))
            except:
                pass

            try:
                for i in range(len(tags_begin)):
                    if tags_end[i] < tags_begin[i] and i != len(tags_begin) - 1:
                        tags_end[i] = tags_end[i + 1]
                    tags.append(test_str[tags_begin[i] : tags_end[i]])
            except:
                pass

    block_preproc(blocks, key = r'cell_type:code,source:', block_type = 'code')
    block_preproc(tags, key = r'cell_type:markdown,source:', block_type = 'tag')
    out = pd.DataFrame(data = {'code_block': blocks, 'tag': tags})

    for i in range(len(blocks)):
        if '#' in blocks[i]:
            comments, no_preproc_comments = comment_finder(blocks[i])
            if len([x for x in out.loc[i, 'tag'].split()]) < 10:
                comments.append(out.loc[i, 'tag'])
            out.at[i, 'tag'] = comments
            for comment in no_preproc_comments:
                out.at[i, 'code_block'] = out.loc[i, 'code_block'].replace(comment, '')
    return out

#################################################################################################################
#----------------------------------------------- PARSING KERNELS -----------------------------------------------#
#################################################################################################################
'''                         FOR THE FINAL RUN
df_1 = pd.read_csv('~/Desktop/kaggle_kernels/kaggle_kernels_hotness.csv')
df_2 = pd.read_csv('~/Desktop/kaggle_kernels/kaggle_kernels_scoreAscending.csv')
df_3 = pd.read_csv('~/Desktop/kaggle_kernels/kaggle_kernels_scoreDescending.csv')
df_4 = pd.read_csv('~/Desktop/kaggle_kernels/kaggle_kernels_voteCount.csv')
df_5 = pd.read_csv('~/Desktop/kaggle_kernels/kk_2_4_2020.csv')
df_6 = pd.read_csv('~/Desktop/kaggle_kernels/kk_4_4_2020.csv')
df_7 = pd.read_csv('~/Desktop/kaggle_kernels/kk_6_4_2020.csv')
df_8 = pd.read_csv('~/Desktop/kaggle_kernels/kk_8_4_2020.csv')

df = pd.concat([df_1, df_2, df_3, df_4, df_5, df_6, df_7, df_8])
'''
'''                         FOR MULTIPLE KERNEL TEST RUN
df = pd.read_csv('~/Desktop/kk_duplicate.csv')
'''
'''                         FOR 1 KERNEL TEST RUN
df = pd.read_csv('~/Desktop/kk.csv')
'''
df = pd.read_csv('~/Desktop/kk.csv')
df.drop_duplicates(subset = 'ref', inplace = True)
df.sort_values(by = 'totalVotes', inplace = True, ascending = False)

res = []
kernels = df.iloc[:, 0]
for i in range(len(kernels)):
    start_time = time.time()
    res.append(notebook_parse(kernels[i]))
    end_time = time.time()
    print("notebook: #", i, "number of code blocks", len(res[i]), "time: ", end_time - start_time)

out_df = pd.concat(res)

out_df = out_df[out_df['code_block'].astype(bool)]
out_df = out_df[out_df['tag'].astype(bool)]

out_df.to_csv('~/Desktop/code_blocks.csv', sep='\t', encoding='utf-8')
out_df.to_json('~/Desktop/code_blocks.json', orient = 'index')
