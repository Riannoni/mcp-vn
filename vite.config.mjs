import {defineConfig} from "vite";
import {viteSingleFile} from "vite-plugin-singlefile";
export default defineConfig({
 root:"web",
 plugins:[viteSingleFile()],
 build:{outDir:"../dist",emptyOutDir:true,cssCodeSplit:false,rollupOptions:{input:"web/index.html"}}
});
