const MiniCssExtractPlugin = require("mini-css-extract-plugin");

module.exports = {
    plugins: [new MiniCssExtractPlugin({
      filename: '[name].css',
    })],
    entry: {
        "openCLIP-indexer": "./frontend-src/jsx/openCLIP-indexer.jsx",
        "album-edit": "./frontend-src/jsx/album-edit.jsx",
        "visuals": "./frontend-src/sass/visuals.sass",
        "tag-edit": "./frontend-src/sass/tag-edit.sass",
    },
    module: {
        rules: [
            {
                test: /\.jsx$/,
                use: "babel-loader",
            },
            {
                test: /\.s[ac]ss$/i,
                use: [
                  // Creates `style` nodes from JS strings
                  //"style-loader",
                  MiniCssExtractPlugin.loader,
                  // Translates CSS into CommonJS
                  "css-loader",
                  // Compiles Sass to CSS
                  "sass-loader",
                ],
            },
            {
                test: /\.(svg|png|jpg|jpeg|gif)$/,
                type: "asset/inline",
            },
            {
                test: /\.css$/i,
                use: ["style-loader", "css-loader"],
            },
        ],
    },
    output: {
        path: __dirname + "/static/dist",
        filename: "[name].bundle.js",
    },
};
