'use strict'; // Enable strict mode for this file, prevent memory leakages

// Imports the Google Cloud client library
const dialogflow = require('@google-cloud/dialogflow-cx').v3beta1;
const express = require('express');
const bodyParser = require('body-parser');
const path = require('path');
const fs = require('fs');

const archiver = require('archiver');
const { spawn } = require('child_process');  // for running python script
const { exec } = require('child_process');

// Read environment variables from .env file
const ENV_FILE = path.join(__dirname, '.env.local');
require('dotenv').config({ path: ENV_FILE });

const app = express();
const port = 3000;

// Add CORS handling
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*"); // Allow requests from any origin.  In production, be more restrictive.
  res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept");
  res.header("Access-Control-Allow-Methods", "GET, POST, OPTIONS"); // Allow specified methods
  if (req.method === 'OPTIONS') {
    res.sendStatus(200); // Respond to preflight requests
  } else {
    next();
  }
});

// Use body-parser to parse JSON bodies
app.use(bodyParser.json());

// Configure this to your project, location, agent, and session
const projectId = process.env.REACT_APP_DF_PROJECT_ID
const location = process.env.REACT_APP_DF_LOCATION
const agentId = process.env.REACT_APP_DF_AGENT_ID
const languageCode = 'en'; // Replace with your agent's language code
const environment = process.env.REACT_APP_DF_ENVIRONMENT

// Instantiates a session client
const sessionClient = new dialogflow.SessionsClient({
    apiEndpoint: process.env.REACT_APP_DF_ENDPOINT
});

// ***************************************************
// THIS IS USING DRAFT ENVIRONMENT (DEV)

async function detectIntentText(sessionId, text) {
  const sessionPath = sessionClient.projectLocationAgentSessionPath(
    projectId,
    location,
    agentId,
    sessionId
  );

  const request = {
    session: sessionPath,
    queryInput: {
      text: {
        text: text,
      },
      languageCode,
    },
  };

  const [response] = await sessionClient.detectIntent(request);
  console.log(`User Query: ${text}`);
  for (const message of response.queryResult.responseMessages) {
    if (message.text) {
      console.log(`Agent Response: ${message.text.text}`);
    }
  }

  return response.queryResult;
}


// ACTUAL POST REQUEST HANDLER
app.post('/api', async (req, res) => {
  const {userId, sessionId, text, effective_tab, effective_summary_items } = req.body;

    if (!sessionId || !text) {
        return res.status(400).send({ error: 'Missing sessionId or text' });
    }
    let turns = {
      user:text,
      bot:""
    }
    console.log("|Received Post Request From Frontend @:", generateTimeStamp(),"|SessionId:",sessionId)
    try {
      // Create a timeout promise
      console.log("Sent Post Request to Dialogflow Core Agent @:", generateTimeStamp(),"|SessionId:",sessionId);

      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => {
        reject(new Error('Dialogflow request timed out after 60 seconds'));
      }, 300000);
      });
    // Race the Dialogflow request against the timeout
      const dialogflowResponse = await Promise.race([
        detectIntentText(sessionId, text),
        timeoutPromise
        ]);

      const responses = dialogflowResponse.responseMessages;
      let extractedProcessedResponse = {}
      let textResponse =''
      generateLog(`${sessionId}/raw_responses`,JSON.stringify(dialogflowResponse),JSON.stringify(turns));
      

      if (responses && responses.length > 0) {
        const firstResponse = responses[0];
  
        
        if (firstResponse.text && Array.isArray(firstResponse.text.text) && firstResponse.text.text.length > 0) {
          textResponse = firstResponse.text.text[0];    

        }

        extractedProcessedResponse = await responseParserPython(dialogflowResponse) // AWAIT HERE
        generateLog(`${sessionId}/processor_logs`,JSON.stringify(extractedProcessedResponse),`{"userMessage":"${text}"}`);

        let {message,payload,tab,summaryItems} = generatePayload(dialogflowResponse,extractedProcessedResponse,textResponse);
        tab = tab?tab:(effective_tab?effective_tab:"start");
        const payloadResponse = payload?payload:[];
        const summary = summaryItems?summaryItems:(effective_summary_items?effective_summary_items:[]);
        // CHECK IF PROCESSED MESSAGE IS VALID ELSE USE RAW RESPONSE MESSAGE FROM BOT
        let useResponseTextMessage = message?message:textResponse
        let strucResponse = struct_response(useResponseTextMessage,payloadResponse,tab,summary,textResponse);

        // let struc_response = struct_response(textResponse, payloadResponse);
        console.log("sessionId:",sessionId, "| user query:",text)
        console.log("generated text response: ", textResponse)
        console.log("generated Payload: ", JSON.stringify(payloadResponse))

        console.log("Sent Response to Frontend @:", generateTimeStamp(),"|SessionId:",sessionId);

        res.json(strucResponse);
        
        let turns = {
          user:text,
          bot:textResponse
        }
        
        // generateLog(sessionId,JSON.stringify(dialogflowResponse),JSON.stringify(turns));        
        generateLog(`${sessionId}/sample_input_to_fe`,JSON.stringify(strucResponse),JSON.stringify(turns));

  
      } else {
        // res.status(404).json({ message: 'No response messages from Dialogflow.' });
        let error_res = struct_response("I am sorry, I did not understand that, can you say that again?");
        // let error_res = struct_response(`Dialogflow Response : ${JSON.stringify(responses)}`);
        res.json(error_res);
      }
    } catch (error) {
        console.error('ERROR:', error);
        let error_res = struct_response("I am sorry, I did not understand that, can you say that again?");
        res.json(error_res);
    }
});



// ****************************************//
app.get('/hello', (req, res) => {
  res.send('Dialogflow CX Express Server is running!');
});

// Serve static files from the 'public' directory
app.use(express.static('public'));

// Endpoint to list session folders for download
app.get('/downloads', (req, res) => {
  const logsDir = path.join(__dirname, 'downloads');
  fs.readdir(logsDir, { withFileTypes: true }, (err, dirents) => {
      if (err) {
          console.error("Could not list the logs directory.", err);
          return res.status(500).send('Error listing session folders');
      }

      let sessionListHtml = '<ul>';
      // Filter for directories only
      dirents.filter(dirent => dirent.isDirectory()).forEach(dirent => {
          const sessionFolder = dirent.name;
          sessionListHtml += `<li><a href="/downloads/${sessionFolder}">${sessionFolder}</a></li>`;
      });
      sessionListHtml += '</ul>';

      const html = `
      <!DOCTYPE html>
      <html>
      <head>
          <title>Downloads</title>
      </head>
      <body>
          <h1>Available Session Folders</h1>
          ${sessionListHtml}
      </body>
      </html>
      `;

      res.send(html);
  });
});

// Endpoint to download a specific file within a session folder
app.get('/download/:sessionFolder/:filename', (req, res) => {
    const { sessionFolder, filename } = req.params;
    const filePath = path.join(__dirname, 'downloads', sessionFolder, filename);

    fs.access(filePath, fs.constants.F_OK, (err) => {
        if (err) {
            console.error("File does not exist:", err);
            return res.status(404).send('File not found');
        }

        res.download(filePath, (err) => {
            if (err) {
                console.error("Error during file download:", err);
                res.status(500).send('Error during file download');
            }
        });
    });
});


/********************************************************/
// Endpoint to download a specific session folder
app.get('/downloads/:folderName', (req, res) => {
  const folderName = req.params.folderName;
  const folderPath = path.join(__dirname,'downloads',folderName);

  console.log("FOLDER PAAAATH",folderPath)

  if (!fs.existsSync(folderPath)) {
    return res.status(404).send('Folder not found');
  }

  const archive = archiver('zip', {
    zlib: { level: 9 } // Sets the compression level.
  });

  res.attachment(`${folderName}.zip`);
  archive.pipe(res);

  archive.directory(folderPath, false);
  archive.finalize();
});
/*******************************************************/

function checkDataType(data) {
  if (typeof data === 'string') {
    return 'text';
  } else if (typeof data === 'object' && data !== null && !Array.isArray(data)) {
    return 'object';
  } else {
    return 'other';
  }
}

function struct_response(text_Response,payloadArray,tabText,summaryArray,textResponse){
  return { 
    fulfillment_response: {
      textResponse:text_Response,
      payload:payloadArray,
      tab:tabText,
      summary:summaryArray,
      originalTextResponse:textResponse
    }
  };
};

function parseStringToJson(str) {
  try {
    const jsonObject = JSON.parse(str);
    return jsonObject;
  } catch (error) {
    console.error("Error parsing JSON string:", error);
    return null; // Or handle the error as needed
  }
}

function generateTimeStamp(){
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  return timestamp
}
function generateLog(foldername, data, text) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `log-${timestamp}.txt`;
  const dirPath = path.join(__dirname, `downloads/${foldername}`);
  const filePath = path.join(dirPath, filename);
  const masterFilePath = path.join(dirPath, '0-transcript.txt');

  try {
    // Create the directory if it doesn't exist
    fs.mkdirSync(dirPath, { recursive: true });

    // Write data to the timestamped log file
    fs.writeFileSync(filePath, data, 'utf8');
    console.log(`Log file created: ${filePath}`);

    // Check if master.txt exists
    if (fs.existsSync(masterFilePath)) {
      // Append text to master.txt
      fs.appendFileSync(masterFilePath, text + '\n', 'utf8');
      console.log(`Appended to master.txt: ${masterFilePath}`);
    } else {
      // Create master.txt and write text
      fs.writeFileSync(masterFilePath, text + '\n', 'utf8');
      console.log(`Created 0-transcript.txt: ${masterFilePath}`);
    }
  } catch (err) {
    console.error('Error writing log file:', err);
  }
}


function extractPlaybookId(jsonObject) {
  try {
    const playbookInvocation = jsonObject.generativeInfo.actionTracingInfo.actions.find(
      (action) => action.playbookInvocation
    );

    if (playbookInvocation) {
      const playbookPath = playbookInvocation.playbookInvocation.playbook;
      const playbookId = playbookPath.split('/').pop();
      return playbookId;
    } else {
      return null; // Or throw an error, depending on desired behavior
    }

  } catch (error) {
    console.error("Error extracting playbook ID:", error);
    return null; // Or re-throw, or return a default value
  }
}

function extractClientAndCategory(jsonObject) {
  let extractedClientCategory = {}
  let convertedOutput =[]
  try {
    const fields = jsonObject.generativeInfo.actionTracingInfo.actions
      .find(action => action.toolUse?.displayName === 'getLatestClientRecord')
      ?.toolUse.outputActionParameters.fields['200'].structValue.fields;

    if (fields) {
      let client = fields.Client?.stringValue;
      let category = fields.Category?.stringValue;
      extractedClientCategory = { client, category };
    } else {
      extractedClientCategory = {}; // Or throw an error, depending on desired behavior
    }
  } catch (error) {
    console.error("Error extracting data:", error);
    extractedClientCategory = {}; // Handle errors gracefully
  }
  for (const key in extractedClientCategory) {
    if (extractedClientCategory.hasOwnProperty(key)) {
      convertedOutput.push(`${key}:${extractedClientCategory[key]}`);
    }
  }
  return convertedOutput;
}

async function responseParserPython(jsonObject) { // Make this function async
  return new Promise((resolve, reject) => { // Return a Promise
    const pythonProcess = spawn('python3', ['responseParser.py']);

    // Send data to the Python script via stdin
    pythonProcess.stdin.write(JSON.stringify(jsonObject));
    pythonProcess.stdin.end();

    let output = '';

    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`stderr: ${data}`);
      reject(data.toString()); // Reject on error
    });

    pythonProcess.on('close', (code) => {

      try {
        const parsedOutput = JSON.parse(output);

        // Check if parsedOutput is a valid object
        console.log("NEEED TO CHECK HERE OUTPUT",output)
        console.log("NEEED TO CHECK HERE parsedOutput",parsedOutput)
        if (typeof parsedOutput === 'object' && parsedOutput !== null && !Array.isArray(parsedOutput)) {
          resolve(parsedOutput); // Resolve with the parsed output
        } else {
          console.error("Python output is not a valid object:", parsedOutput);
          resolve(null); // or reject, depending on how you want to handle this
        }
      } catch (error) {
        console.error("Error parsing Python output:", error);
        resolve(null); // or reject, depending on how you want to handle this
      }
    });
  });
}


function generatePayload(jsonObject,extractedProcessedResponse,textResponse){
  let message = null;
  let summaryItems = null;
  let payload = [];
  let tab = null;  
  let playbookid = extractPlaybookId(jsonObject);
  let playbookToTabMap = {
    "67df940c-ed22-4189-80a1-c9c866c947d2":"inventory",
    "f5f71095-9182-49fc-b1f4-ed3b59f4980d":"research",
    "779e3d39-2cb8-4e42-964f-3568fdc84303":"brainstorming",
    "45f21efb-4200-4dcc-a77a-091e8c6d4a39":"whitepaper"
  }


  summaryItems = extractClientAndCategory(jsonObject)
  if(playbookid in playbookToTabMap){
    tab = playbookToTabMap[playbookid]
    }
  
  if (extractedProcessedResponse){

  let processorPayload = extractedProcessedResponse['payload']
  let processorMessage = extractedProcessedResponse['message']


  if(processorPayload && processorPayload.length>0){
    payload.push(processorPayload)
  }
  
  if(processorMessage){
    message = processorMessage
  }
  console.log("GENERATE PAYLOAD","MESSAGE|",message,"|PAYLOAD|",payload,"|TAB|",tab,"|SUMMARY|",summaryItems )
  } 
  

  return {"message":message,"payload":payload,"tab":tab,"summaryItems":summaryItems}
}


module.exports = {
  app
};
  