import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/ui/select'

export type AppSelectOption = {
  value: string
  label: string
}

const EMPTY_SELECT_VALUE = '__camxora_empty__'

export function AppSelect(props: {
  id?: string
  value: string
  options: ReadonlyArray<AppSelectOption>
  onChange: (value: string) => void
  placeholder: string
  disabled?: boolean
  triggerClassName?: string
  contentClassName?: string
}): React.JSX.Element {
  const hasCurrentValue = props.options.some((option) => option.value === props.value)
  const selectValue = props.value && hasCurrentValue ? props.value : EMPTY_SELECT_VALUE

  return (
    <Select
      disabled={props.disabled}
      value={selectValue}
      onValueChange={(nextValue) => props.onChange(nextValue === EMPTY_SELECT_VALUE ? '' : nextValue)}
    >
      <SelectTrigger className={props.triggerClassName} id={props.id}>
        <SelectValue placeholder={props.placeholder} />
      </SelectTrigger>
      <SelectContent className={props.contentClassName}>
        <SelectItem value={EMPTY_SELECT_VALUE}>{props.placeholder}</SelectItem>
        {props.options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
