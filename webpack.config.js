module.exports = {
    entry: {
        "openCLIP-indexer": "./frontend-src/jsx/openCLIP-indexer.jsx",
    },
    module: {
        rules: [
            {
                test: /\.jsx$/,
                use: "babel-loader",
            },
            {
                test: /\.(svg|png|jpg|jpeg|gif)$/,
                loader: "file-loader",

                options: {
                    name: "[name].[ext]",
                    outputPath: "../../static/dist",
                },
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
