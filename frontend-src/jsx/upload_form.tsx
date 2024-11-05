import React, {ReactElement, ReactHTML, useId}  from 'react';
import { useState } from "react";
import { createRoot } from 'react-dom/client';


type FileType = File | null;


interface UploadFormProps{
    submittion_allowed: boolean
    file_update_event: (new_file: FileType) => void
}

type SubmitButton = ReactElement<HTMLInputElement> | null;


function UploadForm(props: UploadFormProps){
    function handleFileChange(e: React.ChangeEvent<HTMLInputElement>){
        console.log(e.target.files);
        if (e.target.files.length > 0)
            props.file_update_event(e.target.files[0]);
        else
            props.file_update_event(null);
    }
    function clear_file(){
        props.file_update_event(null);
    }
    const image_field_id = useId()
    const description_field_id = useId()
    const origin_name_field_id = useId()
    const origin_id_field_id = useId()
    const alternate_version_flag_id = useId()
    const submit_button = (props.submittion_allowed) ? <input type="submit" />: null;
    return (
        <form method="post" action="/medialib/upload/uploading" encType="multipart/form-data">
            <label htmlFor={image_field_id}>
                Put file here: 
                <input type="file" name="image-file" id={image_field_id} onChange={handleFileChange}/>
            </label>
            {submit_button}
            <input type="reset" value="Clear" onClick={clear_file}/><br/>
            <label htmlFor={description_field_id}>
                Description: <br />
                <textarea name="description" id={description_field_id}></textarea>
            </label>
            <br />
            <label htmlFor={origin_name_field_id}>
                Origin name: 
                <input type="text" name="origin_name" id={origin_name_field_id}/>
            </label>
            <br />
            <label htmlFor={origin_id_field_id} >
                Origin content ID:
                <input type="text" name="origin_id" id={origin_id_field_id} />
            </label>
            <br />
            <label htmlFor={alternate_version_flag_id}>
                Alternate version 
                <input type="checkbox" name="alternate_version" id={alternate_version_flag_id} />
            </label>
        </form>
    )
}

interface FileInfoProps{
    file: File
}

function FileInfoView(props: FileInfoProps){
    return <>
        <h2>File Info</h2>
        <div>Title: <b>{props.file.name}</b></div>
        <div>Size: <b>{Number(props.file.size / 1024).toFixed(2)} KiB</b></div>
        <div>Mime type: <b>{props.file.type}</b></div>
    </>
}

type ImageElementType = ReactElement<HTMLImageElement> | null;

function App(){
    const [current_file, set_current_file] = useState<FileType>(null);
    const [is_image_file, set_image_file_status] = useState<boolean>(false);
    const [submittion_allowed, allow_submittion] = useState<boolean>(false);
    function file_update(new_file: FileType){
        set_current_file(new_file);
        if (new_file != null){
            allow_submittion(true);
            if (new_file.type.startsWith("image/")){
                set_image_file_status(true);
            } else {
                set_image_file_status(false);
            }
        }else{
            set_image_file_status(false);
            allow_submittion(false);
        }
    }
    const image_element = (is_image_file)? 
        <img className="preview-image" src={URL.createObjectURL(current_file)} /> 
        : null;
    const upload_form_props: UploadFormProps = {
        "submittion_allowed": submittion_allowed,
        "file_update_event": file_update
    }
    const file_info_elem = (current_file !== null)? <FileInfoView file={current_file} /> : null;
    return <>
        {image_element}
        <UploadForm {...upload_form_props} />
        {file_info_elem}
    </>
}

const app = <App />

const app_mounting_root_element = document.getElementById("app-container");
const app_mounting_root = createRoot(app_mounting_root_element);

app_mounting_root.render(app);