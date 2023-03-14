let themeSelector = document.getElementById("theme-selector");
let currentTheme = localStorage.getItem("theme");

function applyTheme(themeName){
  if (themeName !== null){
    console.debug(`apply theme "${themeName}"`);
    document.body.classList.add(themeName);
    for (let optionElement of themeSelector.options) {
      if (optionElement.value === themeName){
        optionElement.selected = true;
        break;
      }
    }
  }
}

applyTheme(currentTheme);

themeSelector.onchange = function (event) {
  let newTheme = this.selectedOptions[0].value;
  if (newTheme === "NONE"){
    newTheme = null;
  }
  if (currentTheme !== null){
    document.body.classList.remove(currentTheme);
  }
  currentTheme = newTheme;
  localStorage.setItem("theme", newTheme);
  applyTheme(newTheme);
}