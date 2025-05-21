import json
import re
import sys

def bot_help_formatter(detected_category,final_msg , response_texts):

    if detected_category == "travel":
        output_json = {
            "message": "Okay, what category are you interested in?",
            "payload": [{
                "name": "action_button",
                        "payload":  ["travel_loding_hotel_resort", "travel_lodging_timeshare", "travel_lodging_rental",
                            "travel_agency_tourism","travel_airline", "travel_car_rental"]
            }],
            "originalTextResponse": response_texts
        }
    elif detected_category == "category":
        output_json = {
                "message": "Okay, and what type of category are you interested in?",
                "payload": [{
                    "name": "action_button",
                    "payload": ["Festivals", "Venues", "Both" ]
                }],
                "originalTextResponse": response_texts
        }
    elif detected_category == 'userstory':
        output_json = {
            "message": final_msg,
            "payload": [{
                "name": "action_button",
                "payload": [ "Inventory Search","Insights and Research", "Brainstorming", "Draft Proposal" ]
            }],
            "originalTextResponse" : response_texts
        }
    elif detected_category == 'drafttone':
        output_json = {
            "message": "Okay, great! To start, would you like to choose a tone for the draft proposal?",
            "payload": [{
                "name": "action_button",
                "payload": ["Casual", "Formal", "Creative", "Persuasive", "Logical"]
            }],
            "originalTextResponse" : response_texts
        }
    else:    
        output_json = {}

    return output_json

def flag_bot_help_formatter(input_json):

    travel_keywords = {"travel_loding_hotel_resort", "travel_lodging_timeshare", "travel_lodging_rental", "travel_agency_tourism", "travel_airline", "travel_car_rental"}
    category_keywords = {"festivals", "venues", "both"}
    userstory_keywords = {"inventory search", "insights and research", "draft proposal"}
    brainstorming_keywords = {"brainstorming", "narrative brainstorming"}
    drafttone_keywords = {"casual", "formal", "creative", "persuasive","logical"}

    # Extract response message
    response_messages = input_json.get("responseMessages", [])
    response_texts = []
    final_msg      = []
    for message in response_messages:
        text_list = message.get("text", {}).get("text", [])
        for text_msg in text_list:
            text = text_msg.strip().split('\n')
            filtered_text = text_msg.strip().split('\n')[0]
            
            if text_msg:
                response_texts.append(text_msg)
            if filtered_text:
                final_msg.append(filtered_text)  

    cleaned_text = "_".join(response_texts).lower()

    # Constructing message
    final_msg = " ".join(final_msg)
    detected_category = None

    # Detect travel category
    if all(keyword in cleaned_text for keyword in travel_keywords):
        detected_category = "travel"

    # Detect general category
    elif all(keyword in cleaned_text for keyword in category_keywords):
        detected_category = "category"


    # Detect userstory category: all userstory keywords + either "brainstorming" or "narrative brainstorming" (but not both)
    elif all(keyword in cleaned_text for keyword in userstory_keywords):
        brainstorming_present = sum(keyword in cleaned_text for keyword in brainstorming_keywords) == 1
        if brainstorming_present:
            detected_category = "userstory"

    # Detect draft proposal tone
    elif all(keyword in cleaned_text for keyword in drafttone_keywords):
        detected_category = "drafttone"

    if detected_category in ['travel','category','userstory','drafttone']:
        output_json = bot_help_formatter(detected_category, final_msg , response_texts)
        return output_json
    else:
        return None
def venue_festival_formatter(response_text , actions):
    extracted_values = []
    cleaned_text = ""
    # cleaned_text = re.sub(r'\s*\n\s*', ' ', response_text).strip()
    """Removes the first newline character and all subsequent text."""
    first_newline_index = response_text.find('\n')
    if first_newline_index != -1:
        # Slice the string up to the index of the first newline
        cleaned_text = response_text[:first_newline_index]
    else:
        # If no newline is found, return the original string
        cleaned_text = response_text
    
    for action in actions:
        if action.get("action") == "toolUse" and action.get("toolUse", {}).get("action") == "getVenuesByCategoryStateAndType":
            options = action["toolUse"]["outputActionParameters"]["fields"]["200"]["structValue"]["fields"]["Available options"]["listValue"]["values"]
            for item in options:
                extracted_values.append({
                "venue_name": item['structValue']['fields']['name']['stringValue'],
                "tags": [item['structValue']['fields']['venue_type']['stringValue'],item['structValue']['fields']['market']['stringValue']]
                })
            break
    else:
        extracted_values = []
    
    # Changing Event to Festival
    for item in extracted_values:
        if item['tags'] and item['tags'][0] == 'Event':
            item['tags'][0] = 'Festival'



    # Construct new JSON format
    transformed_data = {
            "message": cleaned_text+ " Please select the ones you are interested in.",
            "payload": [
                [
                    {
                        "name": "action_cards_venues_festivals_both",
                        "payload": extracted_values
                    },
                    {
                        "name": "action_button_venues_festivals_both",
                        "payload": ["Proceed with selection"]
                    }
                ]
            ],
            "originalTextResponse": response_text
    }

    return transformed_data


def inventory_formatter(response_text , actions):
    inventory_list = []
    venues = []
    
    for action in actions:
        if action.get("action") == "toolUse" and action.get("toolUse", {}).get("action") == "getColumnsWithY":
            venue_name = action["toolUse"]["inputActionParameters"]["fields"]["requestBody"]["structValue"]["fields"]["venue_name"]["stringValue"]
            venues.append(venue_name)
            options = action["toolUse"]["outputActionParameters"]["fields"]["200"]["structValue"]["fields"]["columns_with_Y"]["listValue"]["values"]
            for item in options:
                inventory_list.append({
                    "inventory_name": item["stringValue"],
                    "tags": [venue_name]
                })
    
    # Construct new JSON format
    transformed_data = {
            "message": response_text.split('\n')[0],
            "payload": [
                [
                    {
                        "name": "action_cards_inventories",
                        "payload": inventory_list
                    },
                    {
                        "name": "action_button_inventories",
                        "payload": ["Proceed with selection"]
                    }
                ]
            ],
            "originalTextResponse": response_text
    }

    return transformed_data
def client_formatter(get_client_flag , response_text , actions):
    if any(action.get("toolUse", {}).get("action") == "getLatestClientRecord" for action in actions):
        client_info = {}
        tailer = response_text.split("\n")[-1]
        for action in actions:
            if action.get("action") == "toolUse" and action.get("toolUse", {}).get("action") == "getLatestClientRecord":
                client_info = action["toolUse"]["outputActionParameters"]["fields"]["200"]["structValue"]["fields"]
                break
        
        # Extracting necessary fields
        def get_value(field):
            return client_info.get(field, {}).get("stringValue", "")
        
        client_name = get_value("Client")
        if client_name:
            transformed_data = {
                    "message": f"I found the following details for {client_name}.",
                    "payload": [
                        [
                            {
                                "name": "formatted_text",
                                "payload": {
                                    "header": f"{client_name} Details",
                                    "bullet_points": [
                                        f"- Category: {get_value('Category')}",
                                        f"- Type: {get_value('Type')}",
                                        f"- Brand Positioning USP: {get_value('Brand Positioning / USP')}",
                                        f"- Target Audience: {get_value('Target Audience')}",
                                        f"- Budget: {get_value('Budget')}",
                                        f"- Status: {get_value('Status')}",
                                        f"- Program Timing: {get_value('Program Timing')}",
                                        f"- Date Submitted: {get_value('Date Submitted')}",
                                        f"- Program Objectives / KPIs Purpose: {get_value('Program Objectives / KPIs / Purpose')}",
                                        f"- Client: {client_name}",
                                        f"- Sales 1: {get_value('Sales 1')}"
                                    ],
                                }
                            },
                            {
                                "name": "action_button",
                                "payload": ["Proceed" , "Do Not Proceed", "Modify the Client Details"]
                            }
                        ]
                    ],
                    "originalTextResponse": response_text
            }

            return transformed_data
        else:
            return None
    elif get_client_flag:
        # print("client formatter edge case")
        response_text = response_text.replace('"', "").replace(",","").replace(" -","")
        # Converting text format into structured data
        lines = response_text.split("\n")
        formatted_details = {}

        for line in lines[1:-1]:  # Skip the first intro sentence
            key, value = line.split(": ", 1)
            formatted_details[key.strip("\"")] = value.strip("\"")
        
        if formatted_details:

            # Creating the new JSON structure
            transformed_data = {
                "message": lines[0],
                "payload": [
                    [
                        {
                            "name": "formatted_text",
                            "payload": {
                                "bullet_points": [
                                    f"- {key}: {value}" for key, value in formatted_details.items()
                                ],
                            }
                        },
                        {
                            "name": "action_button",
                            "payload": ["Proceed" , "Do Not Proceed", "Modify the Client Details"]
                        }
                    ]
                ],
                "originalTextResponse": response_text
            }   
            return transformed_data
        else:
            return None                    
    else:
        return None
def insights_formatter(data):

    isThereAQuestion = False
    response_text = data["responseMessages"][0]["text"]["text"][0].strip()
    # Remove the unwanted prefix if it appears at the start
    cleaned_text = re.sub(r"^\|-\s*\n\s*", "", response_text)

    insights_msg_end_phrases = ['What else can I help you with?', 'Do you have more research questions?',
                                'Do you have any other questions?']

    end_statement = cleaned_text.split('\n')[-1]
    if end_statement.lower() in (phrase.lower() for phrase in insights_msg_end_phrases) or end_statement.find('?') != -1:
        # Find the last newline
        last_newline_index = cleaned_text.rfind('\n')

        # Keep everything before the last newline
        cleaned_text = cleaned_text[:last_newline_index] if last_newline_index != -1 else cleaned_text

    end_phrase = "Do you have more research questions?"

    # Find the first newline index
    first_double_newline_index = cleaned_text.find('\n\n')


    # Split the text into two parts
    if first_double_newline_index != -1:
        part1 = cleaned_text[:first_double_newline_index].strip()  # Before the first double newline
        part2 = cleaned_text[first_double_newline_index + 1:].strip()  # After the first double newline
    else:
        part1 = ""
        part2 = cleaned_text  

    part2_list = [line.strip() for line in part2.split('\n')]
    # Check if the result is a list
    if len(part2_list) <= 1:
        part2_list = [line.strip() for line in part2.split('.')]

    keywords_to_remove = ["Key points:","Here's what you should know:"]

    part2_list = [x for x in part2_list if x.lower() not in (key_word.lower() for key_word in keywords_to_remove)]

    # Navigate to the required fields
    citations = (
        data.get("responseMessages", [])[1]
        .get("payload", {})
        .get("fields", {})
        .get("richContent", {})
        .get("listValue", {})
        .get("values", [])[0]
        .get("listValue", {})
        .get("values", [])[0]
        .get("structValue", {})
        .get("fields", {})
        .get("citations", {})
        .get("listValue", {})
        .get("values", [])
    )

    # Construct the desired format
    if citations:
        first_citation = citations[0].get("structValue", {}).get("fields", {})
    
    transformed_data = {
            "message": response_text,
            "payload": [
                [
                    {
                        "name": "insights_card",
                        "payload": {
                            "header" : part1,
                            "title": first_citation.get("title", {}).get("stringValue", ""),
                            "subtitle": part2_list,
                            "actionLink": first_citation.get("actionLink", {}).get("stringValue", ""),
                            "tailer" : end_phrase
                        }
                    },
                    {
                        "name": "action_button",
                        "payload": ["Yes", "No"]
                    }
                ]
            ],
    } 

    return transformed_data    
def has_playbook_invocation(data , playbookID):
    actions = data.get("generativeInfo", {}).get("actionTracingInfo", {}).get("actions", [])
    
    for action in actions:
        if action.get("action") == "playbookInvocation" and "playbookInvocation" in action:
            dataPlaybook = action['playbookInvocation']['playbook'].split('/')[-1]
            if dataPlaybook == playbookID:
                return True  # Found at least one playbookInvocation
    
    return False  # No playbookInvocation found
def get_header_content(data):
    result = []
    for subline in data.split('\n'):
        subline = subline.strip().replace("*", "").replace("- ", "").replace('\"', '')
        # # Convert list into a dictionary structure
        if ":" in subline:
            heading, content = subline.split(":", 1)
            result.append({"heading": heading.strip(), "content": content.strip()}) 
    return result  
def brainstorm_formatter(data):
    response_text = data["responseMessages"][0]["text"]["text"][0]
    cleaned_text = re.sub(r"^\|\-\s*", "", response_text.strip())
    if has_playbook_invocation(data ,  "779e3d39-2cb8-4e42-964f-3568fdc84303"):
        ideas = cleaned_text.split("\n")

        transformed_data = {
                "message": ideas[0],
                "payload": [
                    [
                        {
                            "name": "formatted_text",
                            "payload": {
                                "header":"",
                                "bullet_points": ideas[1:-1],
                                "tailer"       : ideas[-1]
                            }                            
                        },
                        {
                            "name": "action_button",
                            "payload": ["Yes", "No"]
                        }
                    ]
                ],
                "originalTextResponse": response_text
        }

        return transformed_data
    else: # No playbook invocation  
        # Based on multiple examples this is how the split between Header and content is generated from LLM
        # Regex to match the first occurrence of \n\n- ** or \n\n** or \n\n-**
        split_pattern = r"\n\n-\s\*\*|\n\n\*\*|\n\n-\*\*|\n\n\*\s*\*\*|\s*\*\*"

        # Split only at the first occurrence
        parts = re.split(split_pattern, cleaned_text, maxsplit=1)
        
        message = parts[0] if len(parts) > 0 else ""
        text    = parts[1] if len(parts) > 1 else ""

        final_result = []
        text = text.replace("**" ,"")
        nested_topics = re.split(r'\n\n[a-zA-Z]+', text.strip())
        if len(nested_topics) > 1:
            # nested Dictionary
            for topic in nested_topics:
                nested_list =  topic.split('\n\n')
                final_result.append({'topic':nested_list[0] , 'content':get_header_content(nested_list[1])})        
            transformed_data = {
                        "message": message.replace('\n',''),
                        "payload":[{
                            "name":"brainstorming_cards2",
                            "payload": final_result                
                        }
                        ],
                        "originalTextResponse": response_text     
                }
        else:
            # Single dictionary
            final_result = get_header_content(nested_topics[0])

            transformed_data = {
                        "message": message.replace('\n',''),
                        "payload":[{
                            "name":"brainstorming_cards",
                            "payload": final_result                
                        }
                        ],
                        "originalTextResponse": response_text     
                }

        return transformed_data         
def draft_formatter(data):
    response_text = data["responseMessages"][0]["text"]["text"][0]
    # Remove leading "|-" and extra whitespace
    cleaned_text = re.sub(r"^\|\-\s*", "", response_text.strip()).replace("**", "").replace("- ", "")
    ideas = cleaned_text.split("\n\n")
    if len(ideas) > 1:
        transformed_data = {
                "message": ideas[0],
                "payload": [
                        {
                                "name": "whitepaper",
                                "content": ideas[1:]
                        }
                ],
                "originalTextResponse": response_text
        }
        return transformed_data
    else:
        return None                                  


def insights_formatter_main(data):

    # Extract Playbook Info
    playbooks = data.get("generativeInfo", {}).get("currentPlaybooks", [])

    # Define target playbooks
    draft_playbook = ["45f21efb-4200-4dcc-a77a-091e8c6d4a39"]
    brainstorm_playbook = ["779e3d39-2cb8-4e42-964f-3568fdc84303"]
    client_info_playbook = ["45193db6-f13d-4714-b579-31eb9b7739a9"]

    # Find the matching playbooks
    draft_flag = [pb for pb in playbooks if pb.split('/')[-1] in draft_playbook]
    brainstorm_flag = [pb for pb in playbooks if pb.split('/')[-1] in brainstorm_playbook]
    get_client_flag = [pb for pb in playbooks if pb.split('/')[-1] in client_info_playbook]

    if not draft_flag:
        draft_flag = has_playbook_invocation(data ,  "45f21efb-4200-4dcc-a77a-091e8c6d4a39")
        

    response_text = data["responseMessages"][0]["text"]["text"][0]
    actions = data.get("generativeInfo", {}).get("actionTracingInfo", {}).get("actions", [])

    keywords = ["Logical", "Persuasive", "Creative", "Formal"]
    tone_flag = [kw for kw in keywords if kw.lower() not in response_text.lower()]

    # Brainstorm JSON
    if brainstorm_flag:
        # print("Brainstorm")
        output_json = brainstorm_formatter(data)        
    # Draft or Brainstorm JSON
    elif not tone_flag:
        # print("Whitepaper Tone buttons")
        output_json = flag_bot_help_formatter(data)
    # Draft Proposal JSON
    elif draft_flag:
        # print("Draft Proposal")
        output_json = draft_formatter(data)
    # Get Client Info JSON
    elif get_client_flag:
        # print("Client Formatter")
        output_json = client_formatter(get_client_flag ,response_text , actions)
    else:
        # Check weather the JSON is general BOT response or not
        is_general_formater = flag_bot_help_formatter(data)
        if is_general_formater:
            # print("general formatting")
            output_json = is_general_formater
        # Check if it's a Venues/Festivals JSON
        elif any(action.get("toolUse", {}).get("action") == "getVenuesByCategoryStateAndType" for action in actions):
            # print("venuefestformatter")
            output_json = venue_festival_formatter(response_text , actions)
        # Check if it's an Inventory JSON
        elif any(action.get("toolUse", {}).get("action") == "getColumnsWithY" for action in actions):
            # print("inventoryformatter")
            output_json = inventory_formatter(response_text , actions)
        # Check if it's a Inventory Insights JSON
        elif any(action.get("toolUse", {}).get("action") == "research-data" for action in actions):
                # print("insightsformatter")
                output_json = insights_formatter(data)
        else:
            # print("Edge case")
            output_json = None

    return output_json



def process_json():
    try:
        data = json.load(sys.stdin)
        
        # Process the data
        outputJson = insights_formatter_main(data)
        # print(outputJson)
        #check if is dict
        if isinstance(outputJson, dict):
          json.dump(outputJson, sys.stdout)
        else:
          json.dump({}, sys.stdout) # return empty object
    except Exception as e:
        # print(f"Error processing JSON: {e}", file=sys.stderr)
        json.dump({}, sys.stdout) # return empty object

if __name__ == "__main__":
    process_json()


