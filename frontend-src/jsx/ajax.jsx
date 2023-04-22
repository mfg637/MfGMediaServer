export async function postJSON(data, url, callback) {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    const result = await response.text();
    console.log("Success:", result);
    callback()
    //window.location.href =
    //  `${window.location.protocol}//${window.location.host}/content_metadata/mlid${this.state.content_id}`;
  } catch (error) {
    console.error("Error:", error);
  }
}