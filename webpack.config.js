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
        "index": "./frontend-src/sass/index_html-visuals.sass",
        "imageViewer": "./frontend-src/jsx/imageViewer.jsx",
        "tagQueryForm": "./frontend-src/jsx/tag_query_form.tsx"
    },
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/,
            },
            {
                test: /\.jsx$/,
                use: "babel-loader",
            },
            {
                test: /\.s[ac]ss$/i,
                use: [
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
