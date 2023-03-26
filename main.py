from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import json
import time
import os.path


# Login to etherscan and auto fill login information if available
def login():
    driver.get('{}/login'.format(baseUrl))
    driver.implicitly_wait(5)
    driver.find_element("id",
                        "ContentPlaceHolder1_txtUserName").send_keys(config['ETHERSCAN_USER'])
    driver.find_element(
        "id", "ContentPlaceHolder1_txtPassword").send_keys(config['ETHERSCAN_PASS'])

    input("Press enter once logged in")


# Retrieve label information and saves as JSON/CSV
def getLabel(label, label_type="account", input_type='single'):

    if ('eth' not in baseUrl):
        getLabelOldFormat(label, label_type=label_type, input_type=input_type)
        return

    baseUrlLabel = baseUrl + '/{}s/label/{}?subcatid={}&size=100&start={}'
    index = 0  # Initialize start index at 0
    table_list = []

    driver.get(baseUrlLabel.format(label_type, label, 'undefined', index))
    driver.implicitly_wait(5)

    # Find all elements using driver.find_elements where class matches "nav-link"
    # This is used to find all subcategories
    elems = driver.find_elements("class name", "nav-link")
    subcat_id_list = []

    # Loop through elems and append all values to subcat_id_list
    for elem in elems:
        elemVal = elem.get_attribute("val")
        # print(elem.text,elemVal,elem.get_attribute("class")) # Used for debugging elements returned
        if (elemVal is not None):
            subcat_id_list.append(elemVal)

    print(label, 'subcat_values:', subcat_id_list)

    # Bug fix: When there's 0 subcat id found aka ONLY MAIN, we manually add 'undefined' to subcat_id_list
    if (len(subcat_id_list) == 0):
        subcat_id_list.append('undefined')

    for table_index, subcat_id in enumerate(subcat_id_list):
        index = 0  # Initialize start index at 0
        driver.implicitly_wait(5)
        driver.get(baseUrlLabel.format(label_type, label, subcat_id, index))
        time.sleep(5)  # TODO: allow customization by args

        while (True):
            print('Index:', index, 'Subcat:', subcat_id)

            try:
                # Select relevant table from multiple tables in the page, based on current table index
                curTable = pd.read_html(driver.page_source)[table_index]
                if label_type == "account":
                    # Remove last item which is just sum
                    curTable = curTable[:-1]
                print(curTable)

                # Retrieve all addresses from table
                elems = driver.find_elements("xpath", "//tbody//a[@href]")
                addressList = []
                addrIndex = len(baseUrl + '/address/')
                for elem in elems:
                    href = elem.get_attribute("href")
                    if (href.startswith('baseUrl/address/')):
                        addressList.append(href[addrIndex:])

                # Replace address column in newTable dataframe with addressList
                curTable['Address'] = addressList
            except Exception as e:
                print(e)
                print(label, "Skipping label due to error")
                return

            table_list.append(curTable)

            # If table is less than 100, then we have reached the end
            if (len(curTable.index) == 100):
                if label_type == "account":
                    index += 100
                    driver.get(baseUrl.format(
                        label_type, label, subcat_id, index))
                if label_type == "token":
                    next_icon_elems = driver.find_elements(
                        "class name", "fa-chevron-right")
                    next_icon_elems[0].click()
                time.sleep(5)  # TODO: allow customization by args
            else:
                break

    df = pd.concat(table_list)  # Combine all dataframes
    df.fillna('', inplace=True)  # Replace NaN as empty string
    df.index = range(len(df.index))  # Fix index for df

    # Prints length and save as a csv
    print(label, 'Df length:', len(df.index))
    df.to_csv(savePath + '{}s/{}.csv'.format(label_type, label))

    # Save as json object with mapping address:nameTag
    if label_type == "account":
        addressNameDict = dict([(address, nameTag)
                                for address, nameTag in zip(df.Address, df['Name Tag'])])
    if label_type == "token":
        addressNameDict = dict([(address, nameTag)
                                for address, nameTag in zip(df.Address, df['Token Name'])])
    with open(savePath + '{}s/{}.json'.format(label_type, label), 'w', encoding='utf-8') as f:
        json.dump(addressNameDict, f, ensure_ascii=True)

    if (input_type == 'single'):
        endOrContinue = input(
            'Type "exit" end to end or "label" of interest to continue')
        if (endOrContinue == 'exit'):
            driver.close()
        else:
            getLabel(endOrContinue, label_type=label_type)


def getLabelOldFormat(label, label_type="account", input_type='single'):
    print('Getting label old format', label)
    baseUrlLabel = baseUrl + '/{}s/label/{}?subcatid=undefined&size=100&start={}'
    index = 0  # Initialize start index at 0
    table_list = []

    while (True):
        print('Index:', index)
        driver.get(baseUrlLabel.format(label_type, label, index))
        driver.implicitly_wait(5)
        try:
            newTable = pd.read_html(driver.page_source)[0]
        except Exception as e:
            print(e)
            print(label, "Skipping label due to error")
            return
        # Remove last item which is just sum
        table_list.append(newTable[:-1])
        index += 100
        if (len(newTable.index) != 101):
            break

    df = pd.concat(table_list)  # Combine all dataframes
    df.fillna('', inplace=True)  # Replace NaN as empty string
    df.index = range(len(df.index))  # Fix index for df

    # Prints length and save as a csv
    print(label, 'Df length:', len(df.index))
    df.to_csv(savePath + '{}s/{}.csv'.format(label_type, label))

    # Save as json object with mapping address:nameTag
    if label_type == "account":
        addressNameDict = dict([(address, nameTag)
                                for address, nameTag in zip(df['Address'], df['Name Tag'])])
    if label_type == "token":
        addressNameDict = dict([(address, nameTag)
                                for address, nameTag in zip(df['Contract Address'], df['Token Name'])])
    with open(savePath + '{}s/{}.json'.format(label_type, label), 'w', encoding='utf-8') as f:
        json.dump(addressNameDict, f, ensure_ascii=True)

    if (input_type == 'single'):
        endOrContinue = input(
            'Type "exit" end to end or "label" of interest to continue')
        if (endOrContinue == 'exit'):
            driver.close()
        else:
            getLabelOldFormat(endOrContinue, label_type=label_type)


# Combines all JSON into a single file combinedLabels.json
def combineAllJson():
    combinedAccountJSON = {}

    # iterating over all files
    for files in os.listdir(savePath + 'accounts'):
        if files.endswith('json'):
            print(files)  # printing file name of desired extension
            with open(savePath + 'accounts/{}'.format(files)) as f:
                dictData = json.load(f)
                for address, nameTag in dictData.items():
                    if address not in combinedAccountJSON:
                        combinedAccountJSON[address] = {
                            'name': nameTag, 'labels': []}
                    combinedAccountJSON[address]['labels'].append(files[:-5])
        else:
            continue

    combinedTokenJSON = {}
    for files in os.listdir(savePath + 'tokens'):
        if files.endswith('json'):
            print(files)  # printing file name of desired extension
            with open(savePath + 'tokens/{}'.format(files)) as f:
                dictData = json.load(f)
                for address, nameTag in dictData.items():
                    if address not in combinedTokenJSON:
                        combinedTokenJSON[address] = {
                            'name': nameTag, 'labels': []}
                    combinedTokenJSON[address]['labels'].append(files[:-5])
        else:
            continue

    combinedAllJSON = {
        key: {**combinedAccountJSON.get(key, {}),
              **combinedTokenJSON.get(key, {})}
        for key in set(list(combinedAccountJSON.keys())+list(combinedTokenJSON.keys()))
    }

    with open(savePath + 'combined/combinedAccountLabels.json', 'w', encoding='utf-8') as f:
        json.dump(combinedAccountJSON, f, ensure_ascii=True)
    with open(savePath + 'combined/combinedTokenLabels.json', 'w', encoding='utf-8') as f:
        json.dump(combinedTokenJSON, f, ensure_ascii=True)
    with open(savePath + 'combined/combinedAllLabels.json', 'w', encoding='utf-8') as f:
        json.dump(combinedAllJSON, f, ensure_ascii=True)

# Retrieves all labels from labelcloud and saves as JSON/CSV


def getAllLabels():
    driver.get(baseUrl + '/labelcloud')
    driver.implicitly_wait(5)

    elems = driver.find_elements("xpath", "//a[@href]")
    labels = []
    labelIndex = len(baseUrl + '/accounts/label/')
    for elem in elems:
        href = elem.get_attribute("href")
        if (href.startswith(baseUrl + '/accounts/label/')):
            labels.append(href[labelIndex:])

    print(labels)
    print('L:', len(labels))

    for label in labels:
        if (os.path.exists(savePath + 'accounts/{}.json'.format(label))):
            print(label, "'s account labels already exist, skipping.")
            continue
        elif label in ignore_list:
            print(label, 'ignored due to large size and irrelevance')
            continue

        getLabel(label, 'account', 'all')
        time.sleep(5)  # Give 5s interval to prevent RL

    for label in labels:
        if (os.path.exists(savePath + 'tokens/{}.json'.format(label))):
            print(label, "'s token labels already exist, skipping.")
            continue
        elif label in ignore_list:
            print(label, 'ignored due to large size and irrelevance')
            continue

        getLabel(label, 'token', 'all')
        time.sleep(5)  # Give 5s interval to prevent RL

    # Proceed to combine all addresses into single JSON after retrieving all.
    combineAllJson()


# Large size: Eth2/gnsos , Bugged: Liqui , NoData: Remaining labels
ignore_list = ['eth2-depositor', 'gnosis-safe-multisig', 'liqui.io', 'education', 'electronics',
               'flashbots', 'media', 'music', 'network', 'prediction-market', 'real-estate', 'vpn', 'beacon-depositor', 'uniswap']

with open('config.json', 'r') as f:
    config = json.load(f)

# Scan site mapping from chain to __scan url
chainMap = {'eth': {'baseUrl': 'https://etherscan.io', 'savePath': './data/etherscan/'},
            'bsc': {'baseUrl': 'https://bscscan.com', 'savePath': './data/bscscan/'},
            'poly': {'baseUrl': 'https://polygonscan.com', 'savePath': './data/polygonscan/'}
            }

if __name__ == "__main__":
    driver = webdriver.Chrome(service=ChromeService(
        ChromeDriverManager().install()))
    targetChain = input('Enter scan site of interest (eth/bsc/poly): ')

    if (targetChain not in chainMap):
        print('Invalid chain input, exiting, please try again with either eth/bsc/poly')
        exit()
    else:
        baseUrl = chainMap[targetChain]['baseUrl']
        savePath = chainMap[targetChain]['savePath']

    login()
    retrievalType = input('Enter retrieval type (single/all): ')
    if (retrievalType == 'all'):
        getAllLabels()
    else:
        singleLabel = input('Enter label of interest: ')
        label_type = input('Enter label type (account/token): ')
        getLabel(singleLabel, label_type)
