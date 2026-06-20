import re

with open(r'd:\Development\Projects\Electron\MusicGenerator\src\pages\Home.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# find <TabsContent value="spectrum"... to the end of the Tabs group (which is around line 2780)
# we can just use string matching or split by lines

lines = code.split('\n')
out_lines = []
skip = False
for line in lines:
    if '<TabsContent value="spectrum"' in line:
        skip = True
    if skip and '</Tabs>' in line:
        # Wait, </Tabs> might be closing the outer tabs? No, the outer tabs is </Tabs>
        # Let's just look for the end of the effects TabsContent.
        pass
        
    if not skip:
        out_lines.append(line)
        
    if skip and '</TabsContent>' in line:
        # this might close one TabsContent. We need to skip spectrum, particles, effects.
        pass

# A safer way: regex to remove <TabsContent value="spectrum" ... </TabsContent>
# Then the same for particles and effects.

code = re.sub(r'<TabsContent value="spectrum".*?</TabsContent>', '', code, flags=re.DOTALL)
code = re.sub(r'<TabsContent value="particles".*?</TabsContent>', '', code, flags=re.DOTALL)
code = re.sub(r'<TabsContent value="effects".*?</TabsContent>', '', code, flags=re.DOTALL)

with open(r'd:\Development\Projects\Electron\MusicGenerator\src\pages\Home.tsx', 'w', encoding='utf-8') as f:
    f.write(code)

print("done")
