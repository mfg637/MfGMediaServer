import React from 'react';
import { useState } from "react";
import { createRoot } from 'react-dom/client';


function UploadForm(){
    return (
        <form>
            <label htmlFor="image-file-field">Put file here:</label>
            <input type="file" name="image-file" id="image-file-field" />
        </form>
    )
}

function App(){
    return <UploadForm />
}

const app = <App />

const app_mounting_root_element = document.getElementById("app-container");
const app_mounting_root = createRoot(app_mounting_root_element);

app_mounting_root.render(app);