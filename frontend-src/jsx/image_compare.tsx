import React, {MouseEventHandler, useEffect} from 'react';
import { useState } from "react";
import { createRoot } from 'react-dom/client';

console.log("IMAGE COMPARE MODULE LOADED");

interface ContentRepresentationUnit {
    file_path: string
    compatibility_level: number | null
    format: string
}

interface ImageData{
    content_id: number
    pathstr: string
    content_type: string
    file_suffix: string
    width: number
    height: number
    representations: ContentRepresentationUnit[]
    source: string
    source_id: string
    download_date: string
    alternate_version: boolean
}

interface CompareResult {
    first_content_id: number
    second_content_id: number
    is_size_equal: boolean
    is_aspect_ratio_equal: boolean
    is_first_larger: boolean
    is_first_newer: boolean
    is_origin_equal: boolean
    both_alternate_version: boolean
    difference: number | null
    no_difference: boolean
}

interface ComparisonDataSerialised{
    image_data: ImageData[],
    compare_results: CompareResult[]
}

let compareData: ComparisonDataSerialised | null = null;
const meta_elems = document.getElementsByTagName("meta");
for (let i = 0; i < meta_elems.length; i++) {
    const metaElement = meta_elems[i];
    const dataName = metaElement.getAttribute("name")
    if (dataName === "compare_data")
        compareData = JSON.parse(metaElement.getAttribute("content"));
}

console.log("compare data", compareData)

interface AssignedComparisonResult {
    results: CompareResult,
    first_content: ImageData,
    second_content: ImageData
}

interface ListRepresentationsProps{
    reprList: ContentRepresentationUnit[]
}

function ListRepresentations(props: ListRepresentationsProps) {
    return (
        <ul>
            {props.reprList.map((repr, index) =>
                <li key={repr.file_path}>Level {repr.compatibility_level}: {repr.format}</li>)
            }
        </ul>
    )
}

function ImageDataBlock(imageData: ImageData){
    return (
        <div className="image-data">
            <div>
                content id: {imageData.content_id}
            </div>
            <div>
                type: {imageData.content_type}
            </div>
            <div>
                suffix: {imageData.file_suffix}
            </div>
            <div>
                size: {imageData.width}x{imageData.height}
            </div>
            <div>
                Downloaded at: {(new Date(imageData.download_date)).toDateString()}
            </div>
            <div>
                Origin: {imageData.source}
            </div>
            <div>
                Origin ID: {imageData.source_id}
            </div>
            <div>
                Representations: <ListRepresentations reprList={imageData.representations} />
            </div>
            <div>
                {imageData.alternate_version?"Alternate version":"Replacement candidate"}
            </div>
        </div>
    )
}

function ComprassionBlock(results: CompareResult) {
    let show_difference = (
        <div >
           Impossible to calculate difference
        </div>
    );
    if (results.difference !== null){
        show_difference = (
            <div 
                className={results.no_difference?"status-good":"status-warning"}
            >
                Difference: {(results.difference * 100).toFixed(2)} %
            </div>
        );
    }
    return (
        <div className="comparison-block">
            <div className={results.is_size_equal?"status-warning":"status-good"}>
                {results.is_size_equal?"Size equal":results.is_first_larger?"First image larger":"Second image larger"}
            </div>
            <div className={results.is_aspect_ratio_equal?"status-warning":"status-good"}>
                {results.is_aspect_ratio_equal?"Aspect ratio is equal":"Different aspect ratios"}
            </div>
            <div>
                {results.is_first_newer?"First content newer":"Second content newer"}
            </div>
            <div className={results.is_origin_equal?"status-warning":"status-good"}>
                {results.is_origin_equal?"Both images from the same origin":"Images were taken from different origins"}
            </div>
            <div className={results.both_alternate_version?"status-important":"status-good"}>
                {results.both_alternate_version?"Both images are alternate versions":"There is an replacement candidate"}
            </div>
            { show_difference }
            <div>
                {!results.both_alternate_version?
                    <a href={`/medialib/mark_alternate?content_id=${results.first_content_id}&content_id=${results.second_content_id}`} >
                        Mark as alternate versions
                    </a>:null
                }
            </div>

        </div>
    )
}

enum ViewMode{
    FIT_WIDTH,
    ORIGINAL_SIZE
}

interface ImageComparisonViewProps{
    first_image: ImageData,
    second_image: ImageData
}

function ImageComparisonView(props: ImageComparisonViewProps) {
    const [viewMode, setViewMode] = useState<ViewMode>(ViewMode.FIT_WIDTH);
    const [opacityLevel, setOpacityLevel] = useState<number>(0.0);

    const MAX_OPACITY = 100;

    function modeChangeEvent(e: React.MouseEvent<HTMLButtonElement>) {
        const currentState: boolean = viewMode == 1;
        const newState: boolean = !currentState;
        setViewMode(+newState);
    }

    function changeOpacityEvent(e: React.ChangeEvent<HTMLInputElement>) {
        const opacityInt = parseInt(e.target.value);
        setOpacityLevel(opacityInt);
    }

    const firstImageStyles = {
        opacity: opacityLevel==MAX_OPACITY?0:1,
    }

    const secondImageStyles = {
        opacity: opacityLevel / MAX_OPACITY,
    }

    return (
        <div className="image-view">
            <div className="controls">
                <button onClick={modeChangeEvent} >Mode: {viewMode === ViewMode.ORIGINAL_SIZE?"ORIGINAL":"FIT"}</button>
                <input type="range" min="0" max={MAX_OPACITY} value={opacityLevel} onChange={changeOpacityEvent}/>
            </div>
            <div className={"image-wrapper " + ((viewMode === ViewMode.FIT_WIDTH)?"fit-image":"")}>
                <img src={`/image/png/${props.first_image.pathstr}`} style={firstImageStyles}/>
                <img src={`/image/png/${props.second_image.pathstr}`} style={secondImageStyles}/>
            </div>
        </div>
    )
}

function ImageComparison(props: AssignedComparisonResult) {
    return (
        <div>
            <ImageDataBlock {...props.first_content} />
            <ComprassionBlock {...props.results} />
            <ImageDataBlock {...props.second_content} />
            <ImageComparisonView first_image={props.first_content} second_image={props.second_content} />
        </div>
    )
}

function ImageComparisonApp(props: ComparisonDataSerialised) {
    let assignedResults: AssignedComparisonResult[] = [];
    for (let result_index = 0; result_index < props.compare_results.length; result_index++) {
        let first_elem_index: number | null = null;
        let second_elem_index: number | null = null;
        for (let i = 0; i < props.image_data.length; i++) {
            if (props.image_data[i].content_id === props.compare_results[result_index].first_content_id){
                first_elem_index = i;
                break;
            }
        }
        for (let i = 0; i < props.image_data.length; i++) {
            if (props.image_data[i].content_id === props.compare_results[result_index].second_content_id){
                second_elem_index = i;
                break;
            }
        }
        if ((first_elem_index === null) || (second_elem_index === null))
            throw new Error("Not founded elements by ID");
        assignedResults.push({
            results: props.compare_results[result_index],
            first_content: props.image_data[first_elem_index],
            second_content: props.image_data[second_elem_index]
        })
    }
    return (
        <>
            {assignedResults.map((value, index) =>
                <ImageComparison {...value} key={index} />)
            }
        </>
    )
}

const app = <ImageComparisonApp {...compareData} />

const ic_mounting_root_element = document.getElementById("application-wrapper");
const ic_mounting_root = createRoot(ic_mounting_root_element);

ic_mounting_root.render(app);
